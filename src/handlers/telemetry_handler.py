import logging
from typing import Any, Dict

from src.services.dynamodb_service import get_tanker, update_tanker
from src.utils.response import build_response, error_response
from src.utils.validators import parse_event_body, validate_required_fields

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Quality thresholds
TDS_LIMIT_PPM = 500.0
TURBIDITY_LIMIT_NTU = 5.0


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    POST /api/tanker/telemetry and AWS IoT Rule trigger (tanker/+/telemetry).
    Processes GPS and water quality metrics:
    - If TDS > 500 or Turbidity > 5.0: valve_locked = True, status = 'FLAGGED'
    - If readings return to normal: clears FLAGGED to 'IN_TRANSIT' (valve stays locked until authorized unlock)
    """
    try:
        data = parse_event_body(event)
    except ValueError as err:
        return error_response(400, str(err))

    # Required fields validation
    required = ["tanker_id", "lat", "lng", "tds", "turbidity"]
    missing_err = validate_required_fields(data, required)
    if missing_err:
        return error_response(400, missing_err)

    tanker_id = str(data["tanker_id"])
    try:
        lat = float(data["lat"])
        lng = float(data["lng"])
        tds = float(data["tds"])
        turbidity = float(data["turbidity"])
    except (ValueError, TypeError) as conv_err:
        return error_response(400, f"Invalid numeric value in telemetry: {conv_err}")

    # Fetch existing tanker record
    tanker = get_tanker(tanker_id)
    if not tanker:
        return error_response(404, f"Tanker '{tanker_id}' not found")

    current_status = tanker.get("status", "IDLE")
    current_valve_locked = tanker.get("valve_locked", True)

    is_contaminated = (tds > TDS_LIMIT_PPM) or (turbidity > TURBIDITY_LIMIT_NTU)

    if is_contaminated:
        # Automatic emergency safety lock & flag
        new_status = "FLAGGED"
        new_valve_locked = True
        logger.warning(
            "Tanker %s CONTAMINATED (TDS: %s, Turbidity: %s). FLAGGED and valve LOCKED.",
            tanker_id, tds, turbidity
        )
    else:
        # Readings are within limits
        if current_status == "FLAGGED":
            # Normalization: clear FLAGGED back to IN_TRANSIT
            # Valve STAYS LOCKED until authorized delivery unlock with customer OTP
            new_status = "IN_TRANSIT"
            new_valve_locked = True
            logger.info(
                "Tanker %s water normalized (TDS: %s, Turbidity: %s). Status cleared to IN_TRANSIT, valve remains locked.",
                tanker_id, tds, turbidity
            )
        else:
            new_status = current_status
            new_valve_locked = current_valve_locked

    updates = {
        "current_location": {"lat": lat, "lng": lng},
        "tds_level": tds,
        "turbidity_level": turbidity,
        "status": new_status,
        "valve_locked": new_valve_locked
    }

    updated_tanker = update_tanker(tanker_id, updates)

    return build_response(200, {
        "message": "Telemetry processed successfully",
        "tanker_id": tanker_id,
        "status": new_status,
        "valve_locked": new_valve_locked,
        "metrics": {
            "tds": tds,
            "turbidity": turbidity,
            "quality_status": "FLAGGED" if is_contaminated else "NORMAL"
        },
        "current_location": {"lat": lat, "lng": lng}
    })
