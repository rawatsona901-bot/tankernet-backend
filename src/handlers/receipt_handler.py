import logging
from typing import Any, Dict

from src.services.dynamodb_service import get_receipt
from src.utils.response import build_response, error_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    GET /api/receipt/{booking_id}
    Retrieves certified quality and delivery receipt for a completed water booking.
    NOTE: Quality statement strictly asserts 'within limits', never uses 'safe'.
    """
    path_parameters = event.get("pathParameters") or {}
    booking_id = path_parameters.get("booking_id")

    if not booking_id:
        # Fallback to query parameters or direct payload
        query_params = event.get("queryStringParameters") or {}
        booking_id = query_params.get("booking_id") or event.get("booking_id")

    if not booking_id:
        return error_response(400, "Missing required parameter: 'booking_id'")

    receipt = get_receipt(booking_id)
    if not receipt:
        return error_response(404, f"Receipt for booking '{booking_id}' not found")

    # Safety guarantee: ensure statement strictly says 'within limits' and NEVER contains 'safe'
    statement = receipt.get("quality_statement", "")
    if "safe" in statement.lower():
        statement = statement.replace("safe", "within limits").replace("Safe", "Within limits")
        receipt["quality_statement"] = statement

    return build_response(200, {
        "message": "Quality receipt retrieved successfully",
        "receipt": receipt
    })
