import json
from decimal import Decimal
from typing import Any, Dict, Optional


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that converts Decimal types to float or int."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def build_response(
    status_code: int,
    body: Any,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Format standard API Gateway response with CORS headers.
    """
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT"
    }
    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body, cls=DecimalEncoder)
    }


def error_response(status_code: int, message: str, details: Optional[Any] = None) -> Dict[str, Any]:
    """
    Format standardized error response.
    """
    body: Dict[str, Any] = {"error": message}
    if details is not None:
        body["details"] = details
    return build_response(status_code, body)
