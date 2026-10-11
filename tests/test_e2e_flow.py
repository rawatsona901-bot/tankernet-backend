import json
import pytest

from src.handlers.booking_handler import handler as booking_handler
from src.handlers.telemetry_handler import handler as telemetry_handler
from src.handlers.unlock_handler import handler as unlock_handler
from src.handlers.receipt_handler import handler as receipt_handler


def test_complete_end_to_end_delivery_lifecycle():
    """
    Full End-to-End Test:
    1. Booking creation (Punjabi/Multilingual intent)
    2. City-scoped IDLE tanker assignment (Delhi)
    3. Transit telemetry: Contamination spike (TDS > 500) -> FLAGGED & valve lock
    4. Recovery telemetry: Normalization (350-420 ppm) -> IN_TRANSIT (valve remains locked)
    5. Arrival within 20m of Lajpat Nagar geocoded target
    6. Customer OTP unlock verification -> Valve unlocks, IoT message dispatches, Receipt created
    7. Receipt retrieval -> Strictly asserts 'within limits', never uses 'safe'
    """

    # -------------------------------------------------------------
    # STEP 1: Citizen creates booking in Punjabi
    # -------------------------------------------------------------
    booking_event = {
        "body": json.dumps({
            "text": "ਮੈਨੂੰ ਲਾਜਪਤ ਨਗਰ ਵਿੱਚ 5000 ਲੀਟਰ ਪਾਣੀ ਚਾਹੀਦਾ ਹੈ ਤੁਰੰਤ",
            "user_name": "Gurpreet Singh"
        })
    }
    resp_booking = booking_handler(booking_event)
    assert resp_booking["statusCode"] == 201, f"Booking creation failed: {resp_booking}"

    booking_data = json.loads(resp_booking["body"])["booking"]
    booking_id = booking_data["booking_id"]
    otp = booking_data["otp"]
    assigned_tanker_id = booking_data["assigned_tanker_id"]
    delivery_loc = booking_data["delivery_location"]

    assert assigned_tanker_id == "TANKER-DEL-01"
    assert booking_data["city"] == "Delhi"
    assert booking_data["volume_liters"] == 5000
    assert booking_data["status"] == "DISPATCHED"
    assert len(otp) == 6

    # -------------------------------------------------------------
    # STEP 2: Tanker encounters contamination spike en route
    # -------------------------------------------------------------
    spike_event = {
        "body": json.dumps({
            "tanker_id": assigned_tanker_id,
            "lat": 28.5470,
            "lng": 77.2290,
            "tds": 555,  # Contamination spike (>500 ppm)
            "turbidity": 5.8
        })
    }
    resp_spike = telemetry_handler(spike_event)
    assert resp_spike["statusCode"] == 200
    spike_data = json.loads(resp_spike["body"])

    assert spike_data["status"] == "FLAGGED"
    assert spike_data["valve_locked"] is True
    assert spike_data["metrics"]["quality_status"] == "FLAGGED"

    # -------------------------------------------------------------
    # STEP 3: Water filtration & recovery (TDS in 350-420 ppm range)
    # -------------------------------------------------------------
    recovery_event = {
        "body": json.dumps({
            "tanker_id": assigned_tanker_id,
            "lat": 28.5580,
            "lng": 77.2370,
            "tds": 385,  # Recovery TDS within 350-420 ppm
            "turbidity": 1.7
        })
    }
    resp_recovery = telemetry_handler(recovery_event)
    assert resp_recovery["statusCode"] == 200
    recovery_data = json.loads(resp_recovery["body"])

    # FLAGGED cleared to IN_TRANSIT, but valve STAYS LOCKED
    assert recovery_data["status"] == "IN_TRANSIT"
    assert recovery_data["valve_locked"] is True

    # -------------------------------------------------------------
    # STEP 4: Arrival within 20m of Lajpat Nagar delivery location
    # -------------------------------------------------------------
    # Target is (28.5677, 77.2433); reporting (28.56772, 77.24332) ~3.5m away
    arrival_event = {
        "body": json.dumps({
            "tanker_id": assigned_tanker_id,
            "lat": 28.56772,
            "lng": 77.24332,
            "tds": 375,  # Clean water at delivery point
            "turbidity": 1.4
        })
    }
    resp_arrival = telemetry_handler(arrival_event)
    assert resp_arrival["statusCode"] == 200

    # -------------------------------------------------------------
    # STEP 5: Customer provides OTP to unlock valve
    # -------------------------------------------------------------
    unlock_event = {
        "body": json.dumps({
            "booking_id": booking_id,
            "tanker_id": assigned_tanker_id,
            "user_otp": otp
        })
    }
    resp_unlock = unlock_handler(unlock_event)
    assert resp_unlock["statusCode"] == 200, f"Unlock failed: {resp_unlock}"

    unlock_data = json.loads(resp_unlock["body"])
    assert unlock_data["valve_locked"] is False
    assert unlock_data["tanker_id"] == assigned_tanker_id
    assert "receipt" in unlock_data

    # -------------------------------------------------------------
    # STEP 6: Retrieve and verify quality delivery receipt
    # -------------------------------------------------------------
    receipt_event = {
        "pathParameters": {"booking_id": booking_id}
    }
    resp_receipt = receipt_handler(receipt_event)
    assert resp_receipt["statusCode"] == 200

    receipt_body = json.loads(resp_receipt["body"])["receipt"]
    statement = receipt_body["quality_statement"]

    # Strict compliance: statement states "within limits" and NEVER "safe"
    assert "within limits" in statement.lower()
    assert "safe" not in statement.lower()
    assert receipt_body["tds"] == 375
    assert receipt_body["tanker_id"] == assigned_tanker_id
    assert receipt_body["verification_metrics"]["geofence_verified"] is True
    assert receipt_body["verification_metrics"]["otp_verified"] is True
