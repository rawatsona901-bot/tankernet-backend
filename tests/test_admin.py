import json
import pytest
from src.handlers.admin_handler import handler
from src.services.dynamodb_service import update_tanker


def test_admin_metrics_summary():
    # Set one tanker to FLAGGED
    update_tanker("TANKER-DEL-02", {
        "status": "FLAGGED",
        "valve_locked": True,
        "tds_level": 550
    })

    event = {}
    resp = handler(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    overview = body["fleet_overview"]
    assert overview["total_tankers"] >= 6
    assert overview["flagged_tankers_count"] >= 1
    assert overview["healthy_tankers_count"] >= 5

    # Check flagged list contains the flagged tanker
    flagged_ids = [t["tanker_id"] for t in body["flagged_tankers"]]
    assert "TANKER-DEL-02" in flagged_ids

    # Check illustrative price caps
    caps = body["regulatory_price_caps"]["caps_by_urgency"]
    assert "LOW" in caps
    assert "MEDIUM" in caps
    assert "HIGH" in caps
    assert caps["LOW"]["max_price_per_1000l_inr"] == 500
    assert caps["MEDIUM"]["max_price_per_1000l_inr"] == 600
    assert caps["HIGH"]["max_price_per_1000l_inr"] == 750
    assert "illustrative" in body["regulatory_price_caps"]["notice"].lower()
