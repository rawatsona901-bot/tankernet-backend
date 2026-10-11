import pytest
from src.utils.geo import (
    haversine_distance_meters,
    is_within_geofence,
    find_nearest_tanker,
)
from src.services.geocode_service import geocode_location


def test_haversine_zero_distance():
    # Identical coordinates should yield 0 meters
    dist = haversine_distance_meters(28.5244, 77.2066, 28.5244, 77.2066)
    assert dist == 0.0


def test_haversine_known_distance():
    # Saket (28.5244, 77.2066) to Lajpat Nagar (28.5677, 77.2433) in Delhi is ~6.0 km
    dist = haversine_distance_meters(28.5244, 77.2066, 28.5677, 77.2433)
    assert 5800 < dist < 6200


def test_geofence_boundary():
    # Target location: Lajpat Nagar (28.5677, 77.2433)
    target = {"lat": 28.5677, "lng": 77.2433}

    # 1. Coordinate ~5m away should pass geofence (<= 20m)
    near_coord = {"lat": 28.56774, "lng": 77.24332}
    within, dist = is_within_geofence(near_coord, target, max_distance_meters=20.0)
    assert within is True
    assert dist <= 20.0

    # 2. Coordinate ~50m away should fail geofence (> 20m)
    far_coord = {"lat": 28.56815, "lng": 77.2433}
    within, dist = is_within_geofence(far_coord, target, max_distance_meters=20.0)
    assert within is False
    assert dist > 20.0


def test_find_nearest_tanker():
    target = {"lat": 28.5244, "lng": 77.2066}  # Saket
    tankers = [
        {"tanker_id": "T-FAR", "current_location": {"lat": 28.5823, "lng": 77.0587}},   # Dwarka
        {"tanker_id": "T-NEAR", "current_location": {"lat": 28.5250, "lng": 77.2070}},  # Saket nearby
    ]
    nearest, dist = find_nearest_tanker(target, tankers)
    assert nearest["tanker_id"] == "T-NEAR"
    assert dist < 100.0


def test_geocode_three_cities():
    # Delhi
    delhi_res = geocode_location("Saket")
    assert delhi_res is not None
    assert delhi_res["city"] == "Delhi"

    # Mumbai
    mumbai_res = geocode_location("Kurla")
    assert mumbai_res is not None
    assert mumbai_res["city"] == "Mumbai"

    # Bengaluru
    blr_res = geocode_location("Whitefield")
    assert blr_res is not None
    assert blr_res["city"] == "Bengaluru"
