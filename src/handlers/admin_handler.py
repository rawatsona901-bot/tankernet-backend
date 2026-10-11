import logging
from typing import Any, Dict

from src.services.dynamodb_service import list_tankers
from src.utils.response import build_response, error_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# =========================================================================
# ILLUSTRATIVE REFERENCE PRICE CAPS
# NOTE: The following price caps are illustrative benchmark values per 1,000L
# designed for municipal regulatory guidance during water crises.
# =========================================================================
ILLUSTRATIVE_PRICE_CAPS_INR = {
    "LOW": {
        "multiplier": 1.0,
        "max_price_per_1000l_inr": 500,
        "description": "Standard delivery (within 24-48 hours)"
    },
    "MEDIUM": {
        "multiplier": 1.2,
        "max_price_per_1000l_inr": 600,
        "description": "Priority delivery (same-day)"
    },
    "HIGH": {
        "multiplier": 1.5,
        "max_price_per_1000l_inr": 750,
        "description": "Emergency/Urgent delivery (immediate dispatch)"
    }
}


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    GET /api/admin/metrics
    Fleet health overview, active vs flagged tanker metrics, and illustrative price caps.
    """
    # Query all tankers across cities
    tankers = list_tankers()

    total_tankers = len(tankers)
    flagged_tankers = [t for t in tankers if t.get("status") == "FLAGGED"]
    healthy_tankers = [t for t in tankers if t.get("status") != "FLAGGED"]

    active_tankers = [
        t for t in tankers
        if t.get("status") in ["IDLE", "IN_TRANSIT", "DELIVERING"]
    ]

    # Status distribution
    status_counts = {
        "IDLE": sum(1 for t in tankers if t.get("status") == "IDLE"),
        "IN_TRANSIT": sum(1 for t in tankers if t.get("status") == "IN_TRANSIT"),
        "DELIVERING": sum(1 for t in tankers if t.get("status") == "DELIVERING"),
        "FLAGGED": len(flagged_tankers)
    }

    # Breakdown by city
    cities = {}
    for t in tankers:
        city = t.get("city", "Unknown")
        if city not in cities:
            cities[city] = {"total": 0, "healthy": 0, "flagged": 0}
        cities[city]["total"] += 1
        if t.get("status") == "FLAGGED":
            cities[city]["flagged"] += 1
        else:
            cities[city]["healthy"] += 1

    metrics_payload = {
        "fleet_overview": {
            "total_tankers": total_tankers,
            "active_tankers_count": len(active_tankers),
            "flagged_tankers_count": len(flagged_tankers),  # RED Alert
            "healthy_tankers_count": len(healthy_tankers),  # GREEN Status
            "status_breakdown": status_counts,
            "city_breakdown": cities
        },
        "flagged_tankers": [
            {
                "tanker_id": t.get("tanker_id"),
                "driver_name": t.get("driver_name"),
                "city": t.get("city"),
                "tds_level": t.get("tds_level"),
                "turbidity_level": t.get("turbidity_level"),
                "valve_locked": t.get("valve_locked", True),
                "location": t.get("current_location")
            }
            for t in flagged_tankers
        ],
        "healthy_tankers": [
            {
                "tanker_id": t.get("tanker_id"),
                "driver_name": t.get("driver_name"),
                "city": t.get("city"),
                "status": t.get("status"),
                "tds_level": t.get("tds_level"),
                "turbidity_level": t.get("turbidity_level")
            }
            for t in healthy_tankers
        ],
        # Price caps marked clearly as illustrative values
        "regulatory_price_caps": {
            "notice": "The price caps below are illustrative benchmark values for municipal guidance.",
            "currency": "INR",
            "base_volume_liters": 1000,
            "caps_by_urgency": ILLUSTRATIVE_PRICE_CAPS_INR
        }
    }

    return build_response(200, metrics_payload)
