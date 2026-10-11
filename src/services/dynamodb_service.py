import os
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Environment variable table names
TANKERS_TABLE_NAME = os.environ.get("TANKERS_TABLE", "TankerNet-Tankers")
BOOKINGS_TABLE_NAME = os.environ.get("BOOKINGS_TABLE", "TankerNet-Bookings")
RECEIPTS_TABLE_NAME = os.environ.get("RECEIPTS_TABLE", "TankerNet-Receipts")


# In-memory store for unit testing & offline execution
_IN_MEMORY_DB = {
    "tankers": {},
    "bookings": {},
    "receipts": {}
}


def is_mock_mode() -> bool:
    """Check if in-memory mock mode is enabled."""
    return os.environ.get("MOCK_DYNAMODB", "false").lower() in ["true", "1", "yes"]


def get_dynamo_resource():
    """Get boto3 DynamoDB resource."""
    import boto3
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT")
    if endpoint_url:
        return boto3.resource("dynamodb", endpoint_url=endpoint_url)
    return boto3.resource("dynamodb")


def reset_in_memory_db():
    """Reset the mock database (used in unit test fixtures)."""
    _IN_MEMORY_DB["tankers"].clear()
    _IN_MEMORY_DB["bookings"].clear()
    _IN_MEMORY_DB["receipts"].clear()
    seed_initial_tankers_in_memory()


def seed_initial_tankers_in_memory():
    """Pre-seed tankers across Delhi, Mumbai, and Bengaluru."""
    initial_tankers = [
        # Delhi Tankers
        {
            "tanker_id": "TANKER-DEL-01",
            "driver_name": "Rajesh Kumar",
            "city": "Delhi",
            "current_location": {"lat": 28.5244, "lng": 77.2066},  # Saket
            "tds_level": 380,
            "turbidity_level": 1.5,
            "valve_locked": True,
            "status": "IDLE"
        },
        {
            "tanker_id": "TANKER-DEL-02",
            "driver_name": "Harpreet Singh",
            "city": "Delhi",
            "current_location": {"lat": 28.5175, "lng": 77.1824},  # Mehrauli
            "tds_level": 395,
            "turbidity_level": 1.8,
            "valve_locked": True,
            "status": "IDLE"
        },
        # Mumbai Tankers
        {
            "tanker_id": "TANKER-BOM-01",
            "driver_name": "Sanjay Patil",
            "city": "Mumbai",
            "current_location": {"lat": 19.0726, "lng": 72.8845},  # Kurla
            "tds_level": 310,
            "turbidity_level": 1.2,
            "valve_locked": True,
            "status": "IDLE"
        },
        {
            "tanker_id": "TANKER-BOM-02",
            "driver_name": "Ganesh Shinde",
            "city": "Mumbai",
            "current_location": {"lat": 19.0560, "lng": 72.9158},  # Govandi
            "tds_level": 330,
            "turbidity_level": 1.4,
            "valve_locked": True,
            "status": "IDLE"
        },
        # Bengaluru Tankers
        {
            "tanker_id": "TANKER-BLR-01",
            "driver_name": "Manjunath Gowda",
            "city": "Bengaluru",
            "current_location": {"lat": 12.9352, "lng": 77.6245},  # Koramangala
            "tds_level": 290,
            "turbidity_level": 1.1,
            "valve_locked": True,
            "status": "IDLE"
        },
        {
            "tanker_id": "TANKER-BLR-02",
            "driver_name": "Venkatesh Rao",
            "city": "Bengaluru",
            "current_location": {"lat": 12.9719, "lng": 77.6412},  # Indiranagar
            "tds_level": 305,
            "turbidity_level": 1.3,
            "valve_locked": True,
            "status": "IDLE"
        }
    ]
    for tanker in initial_tankers:
        _IN_MEMORY_DB["tankers"][tanker["tanker_id"]] = dict(tanker)


# Auto-seed in-memory store on module load
seed_initial_tankers_in_memory()


def _convert_floats_to_decimals(obj: Any) -> Any:
    """Recursively convert float types to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _convert_floats_to_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats_to_decimals(v) for v in obj]
    return obj


# ==================== TANKERS ====================

def get_tanker(tanker_id: str) -> Optional[Dict[str, Any]]:
    if is_mock_mode():
        tanker = _IN_MEMORY_DB["tankers"].get(tanker_id)
        return dict(tanker) if tanker else None

    try:
        table = get_dynamo_resource().Table(TANKERS_TABLE_NAME)
        resp = table.get_item(Key={"tanker_id": tanker_id})
        return resp.get("Item")
    except Exception as exc:
        logger.warning("DynamoDB get_tanker error: %s. Falling back to in-memory store.", exc)
        tanker = _IN_MEMORY_DB["tankers"].get(tanker_id)
        return dict(tanker) if tanker else None


def save_tanker(tanker_data: Dict[str, Any]) -> None:
    tanker_id = tanker_data["tanker_id"]
    _IN_MEMORY_DB["tankers"][tanker_id] = dict(tanker_data)

    if not is_mock_mode():
        try:
            table = get_dynamo_resource().Table(TANKERS_TABLE_NAME)
            table.put_item(Item=_convert_floats_to_decimals(tanker_data))
        except Exception as exc:
            logger.warning("DynamoDB save_tanker error: %s. Updated in-memory store.", exc)


def update_tanker(tanker_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tanker = get_tanker(tanker_id)
    if not tanker:
        return None

    tanker.update(updates)
    save_tanker(tanker)
    return tanker


def list_tankers(city: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    if is_mock_mode():
        all_tankers = list(_IN_MEMORY_DB["tankers"].values())
    else:
        try:
            table = get_dynamo_resource().Table(TANKERS_TABLE_NAME)
            resp = table.scan()
            all_tankers = resp.get("Items", [])
            # If table is empty in non-mock, fall back to in-memory seeded tankers
            if not all_tankers and _IN_MEMORY_DB["tankers"]:
                all_tankers = list(_IN_MEMORY_DB["tankers"].values())
        except Exception as exc:
            logger.warning("DynamoDB list_tankers error: %s. Falling back to in-memory store.", exc)
            all_tankers = list(_IN_MEMORY_DB["tankers"].values())

    filtered = []
    for t in all_tankers:
        if city and t.get("city", "").lower() != city.lower():
            continue
        if status and t.get("status") != status:
            continue
        filtered.append(dict(t))
    return filtered


# ==================== BOOKINGS ====================

def create_booking(booking_data: Dict[str, Any]) -> None:
    booking_id = booking_data["booking_id"]
    _IN_MEMORY_DB["bookings"][booking_id] = dict(booking_data)

    if not is_mock_mode():
        try:
            table = get_dynamo_resource().Table(BOOKINGS_TABLE_NAME)
            table.put_item(Item=_convert_floats_to_decimals(booking_data))
        except Exception as exc:
            logger.warning("DynamoDB create_booking error: %s. Updated in-memory store.", exc)


def get_booking(booking_id: str) -> Optional[Dict[str, Any]]:
    if is_mock_mode():
        booking = _IN_MEMORY_DB["bookings"].get(booking_id)
        return dict(booking) if booking else None

    try:
        table = get_dynamo_resource().Table(BOOKINGS_TABLE_NAME)
        resp = table.get_item(Key={"booking_id": booking_id})
        return resp.get("Item")
    except Exception as exc:
        logger.warning("DynamoDB get_booking error: %s. Falling back to in-memory store.", exc)
        booking = _IN_MEMORY_DB["bookings"].get(booking_id)
        return dict(booking) if booking else None


def update_booking(booking_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    booking = get_booking(booking_id)
    if not booking:
        return None

    booking.update(updates)
    create_booking(booking)
    return booking


# ==================== RECEIPTS ====================

def create_receipt(receipt_data: Dict[str, Any]) -> None:
    booking_id = receipt_data["booking_id"]
    _IN_MEMORY_DB["receipts"][booking_id] = dict(receipt_data)

    if not is_mock_mode():
        try:
            table = get_dynamo_resource().Table(RECEIPTS_TABLE_NAME)
            table.put_item(Item=_convert_floats_to_decimals(receipt_data))
        except Exception as exc:
            logger.warning("DynamoDB create_receipt error: %s. Updated in-memory store.", exc)


def get_receipt(booking_id: str) -> Optional[Dict[str, Any]]:
    if is_mock_mode():
        receipt = _IN_MEMORY_DB["receipts"].get(booking_id)
        return dict(receipt) if receipt else None

    try:
        table = get_dynamo_resource().Table(RECEIPTS_TABLE_NAME)
        resp = table.get_item(Key={"booking_id": booking_id})
        return resp.get("Item")
    except Exception as exc:
        logger.warning("DynamoDB get_receipt error: %s. Falling back to in-memory store.", exc)
        receipt = _IN_MEMORY_DB["receipts"].get(booking_id)
        return dict(receipt) if receipt else None
