import datetime
import logging
import random
import uuid
from typing import Any, Dict

from src.services.bedrock_service import parse_booking_text
from src.services.dynamodb_service import (
    create_booking,
    list_tankers,
    update_tanker,
)
from src.services.geocode_service import geocode_location
from src.utils.geo import find_nearest_tanker
from src.utils.response import build_response, error_response
from src.utils.validators import parse_event_body, validate_required_fields

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    POST /api/booking/create
    Free-text booking extraction -> geocode -> nearest city-aware tanker assignment -> OTP generation.
    """
    try:
        body = parse_event_body(event)
    except ValueError as err:
        return error_response(400, str(err))

    # Free text can be passed in 'text', 'prompt', or 'message'
    booking_text = body.get("text") or body.get("prompt") or body.get("message")
    if not booking_text:
        return error_response(400, "Missing required booking text ('text')")

    user_name = body.get("user_name", "Resident")

    # 1. Parse free text using Bedrock / Local Fallback
    parsed_intent = parse_booking_text(booking_text)
    raw_location = parsed_intent.get("location", "Saket")
    volume_liters = parsed_intent.get("volume", 5000)
    urgency = parsed_intent.get("urgency", "MEDIUM")

    # 2. Geocode location to coordinates and city
    geocoded = geocode_location(raw_location)
    if not geocoded:
        return error_response(
            400,
            f"Could not resolve delivery location: '{raw_location}'. Please provide a supported area in Delhi, Mumbai, or Bengaluru.",
            details={"supported_areas": ["Delhi: Dwarka Sec 10, Saket, Lajpat Nagar, Mehrauli",
                                          "Mumbai: Mankhurd, Govandi, Kurla, Andheri East",
                                          "Bengaluru: Whitefield, Bellandur, Koramangala, Indiranagar"]}
        )

    delivery_coords = {"lat": geocoded["lat"], "lng": geocoded["lng"]}
    delivery_city = geocoded["city"]

    # 3. Generate 6-digit numeric OTP
    otp = f"{random.randint(100000, 999999):06d}"
    booking_id = f"BOOK-{uuid.uuid4().hex[:8].upper()}"

    # 4. Find nearest IDLE tanker strictly in the SAME city
    idle_city_tankers = list_tankers(city=delivery_city, status="IDLE")
    assigned_tanker, distance_meters = find_nearest_tanker(delivery_coords, idle_city_tankers)

    if assigned_tanker:
        assigned_tanker_id = assigned_tanker["tanker_id"]
        booking_status = "DISPATCHED"
        # Update tanker status to IN_TRANSIT
        update_tanker(assigned_tanker_id, {
            "status": "IN_TRANSIT",
            "current_booking_id": booking_id
        })
        logger.info(
            "Assigned tanker %s to booking %s in %s (distance: %s meters)",
            assigned_tanker_id, booking_id, delivery_city, distance_meters
        )
    else:
        assigned_tanker_id = None
        booking_status = "PENDING"
        logger.warning("No IDLE tanker found in %s for booking %s", delivery_city, booking_id)

    # 5. Save booking record in DynamoDB
    booking_record = {
        "booking_id": booking_id,
        "user_name": user_name,
        "raw_text": booking_text,
        "delivery_location": delivery_coords,
        "delivery_area": geocoded["display_name"],
        "city": delivery_city,
        "volume_liters": volume_liters,
        "urgency": urgency,
        "status": booking_status,
        "assigned_tanker_id": assigned_tanker_id,
        "otp": otp,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    create_booking(booking_record)

    return build_response(201, {
        "message": "Booking created successfully",
        "booking": booking_record,
        "dispatch_details": {
            "assigned_tanker_id": assigned_tanker_id,
            "distance_meters": distance_meters,
            "status": booking_status
        }
    })
