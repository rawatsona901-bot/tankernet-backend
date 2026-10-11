import json
import pytest
from src.handlers.telemetry_handler import handler
from src.services.dynamodb_service import get_tanker, update_tanker


def test_telemetry_normal_readings():
    tanker_id = "TANKER-DEL-01"
    event = {
        "body": json.dumps({
            "tanker_id": tanker_id,
            "lat": 28.5244,
            "lng": 77.2066,
            "tds": 380,
            "turbidity": 1.5
        })
    }
    resp = handler(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "IDLE"
    assert body["metrics"]["quality_status"] == "NORMAL"

    tanker = get_tanker(tanker_id)
    assert tanker["tds_level"] == 380
    assert tanker["turbidity_level"] == 1.5


def test_telemetry_contamination_spike_flags_and_locks():
    tanker_id = "TANKER-DEL-01"
    # Inject high TDS (> 500 ppm)
    event = {
        "body": json.dumps({
            "tanker_id": tanker_id,
            "lat": 28.5470,
            "lng": 77.2290,
            "tds": 560,
            "turbidity": 2.0
        })
    }
    resp = handler(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "FLAGGED"
    assert body["valve_locked"] is True
    assert body["metrics"]["quality_status"] == "FLAGGED"

    tanker = get_tanker(tanker_id)
    assert tanker["status"] == "FLAGGED"
    assert tanker["valve_locked"] is True


def test_telemetry_turbidity_spike_flags_and_locks():
    tanker_id = "TANKER-DEL-02"
    # Inject high Turbidity (> 5.0 NTU)
    event = {
        "body": json.dumps({
            "tanker_id": tanker_id,
            "lat": 28.5175,
            "lng": 77.1824,
            "tds": 350,
            "turbidity": 6.2
        })
    }
    resp = handler(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "FLAGGED"
    assert body["valve_locked"] is True


def test_telemetry_recovery_clears_flagged_to_in_transit_valve_stays_locked():
    """
    CRITICAL USER REQUIREMENT:
    If readings return to normal (TDS<=500, turbidity<=5),
    clear FLAGGED back to IN_TRANSIT, but valve stays locked until a successful unlock.
    """
    tanker_id = "TANKER-DEL-01"

    # 1. First, flag the tanker
    update_tanker(tanker_id, {
        "status": "FLAGGED",
        "valve_locked": True,
        "tds_level": 550,
        "turbidity_level": 5.5
    })
    flagged_tanker = get_tanker(tanker_id)
    assert flagged_tanker["status"] == "FLAGGED"
    assert flagged_tanker["valve_locked"] is True

    # 2. Transmit recovery telemetry within 350-420 ppm
    recovery_event = {
        "body": json.dumps({
            "tanker_id": tanker_id,
            "lat": 28.5580,
            "lng": 77.2370,
            "tds": 385,
            "turbidity": 1.8
        })
    }
    resp = handler(recovery_event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    # Verified: Status cleared back to IN_TRANSIT
    assert body["status"] == "IN_TRANSIT"
    # Verified: Valve remains locked!
    assert body["valve_locked"] is True

    updated_tanker = get_tanker(tanker_id)
    assert updated_tanker["status"] == "IN_TRANSIT"
    assert updated_tanker["valve_locked"] is True
