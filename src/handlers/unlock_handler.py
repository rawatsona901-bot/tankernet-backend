import datetime
import logging
from typing import Any, Dict

from src.services.dynamodb_service import (
    create_receipt,
    get_booking,
    get_tanker,
    update_booking,
    update_tanker,
)
from src.services.iot_service import publish_valve_unlock
from src.utils.geo import is_within_geofence
from src.utils.response import build_response, error_response
from src.utils.validators import parse_event_body, validate_otp_format, validate_required_fields

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_UNLOCK_DISTANCE_METERS = 20.0
MAX_PERMISSIBLE_TDS = 500.0
MAX_PERMISSIBLE_TURBIDITY = 5.0


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    POST /api/tanker/unlock
    Verifies OTP + 20m Geofence + TDS <= 500 ppm.
    On success, unlocks valve, sends IoT MQTT command, creates Receipt, and completes booking.
    """
    try:
        data = parse_event_body(event)
    except ValueError as err:
        return error_response(400, str(err))

    required = ["booking_id", "tanker_id", "user_otp"]
    missing_err = validate_required_fields(data, required)
    if missing_err:
        return error_response(400, missing_err)

    booking_id = str(data["booking_id"]).strip()
    tanker_id = str(data["tanker_id"]).strip()
    user_otp = str(data["user_otp"]).strip()

    # 1. Fetch Booking
    booking = get_booking(booking_id)
    if not booking:
        return error_response(404, f"Booking '{booking_id}' not found")

    if booking.get("status") == "COMPLETED":
        return error_response(400, "Booking is already completed")

    if booking.get("status") == "CANCELLED":
        return error_response(400, "Booking has been cancelled")

    if booking.get("assigned_tanker_id") != tanker_id:
        return error_response(
            400,
            f"Tanker mismatch: Tanker '{tanker_id}' is not assigned to booking '{booking_id}'"
        )

    # 2. Fetch Tanker
    tanker = get_tanker(tanker_id)
    if not tanker:
        return error_response(404, f"Tanker '{tanker_id}' not found")

    # 3. VERIFICATION CHECK: OTP Validation
    expected_otp = str(booking.get("otp", "")).strip()
    if user_otp != expected_otp:
        logger.warning("Unlock failed: Invalid OTP for booking %s", booking_id)
        return error_response(400, "Authentication failed: Invalid OTP provided")

    # 4. VERIFICATION CHECK: Geofence Distance <= 20m
    tanker_loc = tanker.get("current_location", {})
    delivery_loc = booking.get("delivery_location", {})
    within_geofence, distance_meters = is_within_geofence(
        tanker_loc, delivery_loc, max_distance_meters=MAX_UNLOCK_DISTANCE_METERS
    )

    if not within_geofence:
        logger.warning(
            "Unlock failed: Distance %s m exceeds geofence limit of %s m",
            distance_meters, MAX_UNLOCK_DISTANCE_METERS
        )
        return error_response(
            400,
            f"Geofence violation: Tanker is {distance_meters}m away from delivery point (must be within {MAX_UNLOCK_DISTANCE_METERS}m)",
            details={"actual_distance_meters": distance_meters, "max_allowed_meters": MAX_UNLOCK_DISTANCE_METERS}
        )

    # 5. VERIFICATION CHECK: Water Quality (TDS <= 500 & Turbidity <= 5.0)
    tds = float(tanker.get("tds_level", 0.0))
    turbidity = float(tanker.get("turbidity_level", 0.0))
    tanker_status = tanker.get("status")

    if tanker_status == "FLAGGED" or tds > MAX_PERMISSIBLE_TDS or turbidity > MAX_PERMISSIBLE_TURBIDITY:
        logger.warning(
            "Unlock failed: Quality threshold exceeded (TDS: %s, Turbidity: %s, Status: %s)",
            tds, turbidity, tanker_status
        )
        return error_response(
            400,
            f"Water quality violation: Tanker water parameters exceed permissible limits (TDS: {tds} ppm, Turbidity: {turbidity} NTU)",
            details={"tds": tds, "turbidity": turbidity, "tanker_status": tanker_status}
        )

    # ALL 3 CONDITIONS MET: Execute Unlock
    delivery_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fill_time = booking.get("created_at", delivery_time)

    # Update Tanker State
    update_tanker(tanker_id, {
        "valve_locked": False,
        "status": "DELIVERING"
    })

    # Publish IoT MQTT message
    iot_payload = {
        "action": "UNLOCK",
        "booking_id": booking_id,
        "tanker_id": tanker_id,
        "timestamp": delivery_time,
        "tds": tds,
        "turbidity": turbidity
    }
    iot_result = publish_valve_unlock(tanker_id, iot_payload)

    # Generate Delivery & Quality Receipt
    # NOTE: Quality statement strictly uses "within limits", never "safe"
    quality_statement = f"Water quality parameters are within limits (TDS: {tds} ppm, Turbidity: {turbidity} NTU)"

    receipt_record = {
        "booking_id": booking_id,
        "tanker_id": tanker_id,
        "user_name": booking.get("user_name", "Resident"),
        "delivery_location": delivery_loc,
        "volume_liters": booking.get("volume_liters", 5000),
        "fill_time": fill_time,
        "delivery_time": delivery_time,
        "tds": tds,
        "turbidity": turbidity,
        "quality_statement": quality_statement,
        "verification_metrics": {
            "otp_verified": True,
            "distance_meters": distance_meters,
            "geofence_verified": True,
            "quality_verified": True
        }
    }
    create_receipt(receipt_record)

    # Mark Booking as COMPLETED
    update_booking(booking_id, {
        "status": "COMPLETED",
        "completed_at": delivery_time
    })

    logger.info("Successfully unlocked tanker %s for booking %s. Receipt created.", tanker_id, booking_id)

    return build_response(200, {
        "message": "Valve unlocked successfully. Water delivery initiated.",
        "tanker_id": tanker_id,
        "valve_locked": False,
        "receipt": receipt_record,
        "iot_dispatch": iot_result
    })
