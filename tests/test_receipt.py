import json
import pytest
from src.handlers.receipt_handler import handler
from src.services.dynamodb_service import create_receipt


def test_receipt_statement_asserts_within_limits_and_never_safe():
    booking_id = "BOOK-RECEIPT-001"
    create_receipt({
        "booking_id": booking_id,
        "tanker_id": "TANKER-DEL-01",
        "fill_time": "2026-10-10T10:00:00Z",
        "delivery_time": "2026-10-10T11:00:00Z",
        "tds": 380,
        "turbidity": 1.4,
        "quality_statement": "Water quality parameters are within limits (TDS: 380 ppm, Turbidity: 1.4 NTU)"
    })

    event = {
        "pathParameters": {"booking_id": booking_id}
    }
    resp = handler(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    statement = body["receipt"]["quality_statement"]

    # 1. POSITIVE ASSERTION: Must say "within limits"
    assert "within limits" in statement.lower(), f"Expected 'within limits' in statement: {statement}"

    # 2. NEGATIVE ASSERTION: Must NEVER say "safe"
    assert "safe" not in statement.lower(), f"Word 'safe' was improperly used in receipt statement: {statement}"


def test_receipt_not_found():
    event = {
        "pathParameters": {"booking_id": "NON-EXISTENT"}
    }
    resp = handler(event)
    assert resp["statusCode"] == 404
