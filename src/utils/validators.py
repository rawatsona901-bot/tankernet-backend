import json
import re
from typing import Any, Dict, List, Optional, Tuple


def parse_event_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and parse body from an API Gateway event or direct invocation.
    """
    if not isinstance(event, dict):
        return {}

    body = event.get("body")
    if body is None:
        # Check if the event itself is the payload (e.g., IoT Core trigger or direct test)
        if "tanker_id" in event or "booking_id" in event or "text" in event:
            return event
        return {}

    if isinstance(body, dict):
        return body

    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise ValueError("Malformed JSON body in request")

    return {}


def validate_required_fields(
    data: Dict[str, Any],
    required_fields: List[str]
) -> Optional[str]:
    """
    Check if all required fields are present and not empty/None.
    Returns error message if missing, else None.
    """
    for field in required_fields:
        if field not in data or data[field] is None:
            return f"Missing required field: '{field}'"
        if isinstance(data[field], str) and not data[field].strip():
            return f"Field '{field}' cannot be empty"
    return None


def validate_otp_format(otp: str) -> bool:
    """Validate 6-digit numeric OTP."""
    if not isinstance(otp, str):
        otp = str(otp)
    return bool(re.fullmatch(r"\d{6}", otp.strip()))
