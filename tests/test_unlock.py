import json
import pytest
from src.handlers.unlock_handler import handler
from src.services.dynamodb_service import (
    create_booking,
    get_booking,
    get_receipt,
    get_tanker,
    update_tanker
)


@pytest.fixture
def active_booking():
    booking = {
        "booking_id": "BOOK-TEST-001",
        "user_name": "Aarav Sharma",
        "delivery_location": {"lat": 28.5677, "lng": 77.2433},  # Lajpat Nagar
        "volume_liters": 5000,
        "status": "DISPATCHED",
        "assigned_tanker_id": "TANKER-DEL-01",
        "otp": "654321",
        "created_at": "2026-10-10T12:00:00Z"
    }
    create_booking(booking)

    # Position tanker within 5m of Lajpat Nagar with clean water
    update_tanker("TANKER-DEL-01", {
        "status": "IN_TRANSIT",
        "valve_locked": True,
        "current_location": {"lat": 28.56773, "lng": 77.24332},  # ~3.5 meters
        "tds_level": 375,
        "turbidity_level": 1.4
    })
    return booking


def test_unlock_success(active_booking):
    event = {
        "body": json.dumps({
            "booking_id": "BOOK-TEST-001",
            "tanker_id": "TANKER-DEL-01",
            "user_otp": "654321"
        })
    }
    resp = handler(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    assert body["valve_locked"] is False
    assert "receipt" in body
    assert body["receipt"]["booking_id"] == "BOOK-TEST-001"

    # Verify tanker updated
    tanker = get_tanker("TANKER-DEL-01")
    assert tanker["valve_locked"] is False
    assert tanker["status"] == "DELIVERING"

    # Verify booking marked COMPLETED
    booking = get_booking("BOOK-TEST-001")
    assert booking["status"] == "COMPLETED"

    # Verify receipt saved in DynamoDB
    receipt = get_receipt("BOOK-TEST-001")
    assert receipt is not None
    assert "within limits" in receipt["quality_statement"]


def test_unlock_fails_on_wrong_otp(active_booking):
    event = {
        "body": json.dumps({
            "booking_id": "BOOK-TEST-001",
            "tanker_id": "TANKER-DEL-01",
            "user_otp": "999999"  # Wrong OTP
        })
    }
    resp = handler(event)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "Invalid OTP" in body["error"]


def test_unlock_fails_on_geofence_violation(active_booking):
    # Move tanker 500m away
    update_tanker("TANKER-DEL-01", {
        "current_location": {"lat": 28.5620, "lng": 77.2400}
    })

    event = {
        "body": json.dumps({
            "booking_id": "BOOK-TEST-001",
            "tanker_id": "TANKER-DEL-01",
            "user_otp": "654321"
        })
    }
    resp = handler(event)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "Geofence violation" in body["error"]


def test_unlock_fails_on_water_quality_violation(active_booking):
    # Contaminate tanker water (TDS > 500)
    update_tanker("TANKER-DEL-01", {
        "tds_level": 540,
        "status": "FLAGGED"
    })

    event = {
        "body": json.dumps({
            "booking_id": "BOOK-TEST-001",
            "tanker_id": "TANKER-DEL-01",
            "user_otp": "654321"
        })
    }
    resp = handler(event)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "Water quality violation" in body["error"]
