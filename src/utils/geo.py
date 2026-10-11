import math
from typing import Dict, Any, List, Optional, Tuple


EARTH_RADIUS_METERS = 6371000.0


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth in meters.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_METERS * c


def is_within_geofence(
    loc1: Dict[str, Any],
    loc2: Dict[str, Any],
    max_distance_meters: float = 20.0
) -> Tuple[bool, float]:
    """
    Check if two locations are within a specified geofence threshold in meters.
    Locations are dicts with 'lat' and 'lng' (or 'lon') keys.
    Returns (is_within, distance_in_meters).
    """
    lat1 = float(loc1.get("lat", 0.0))
    lon1 = float(loc1.get("lng", loc1.get("lon", 0.0)))
    lat2 = float(loc2.get("lat", 0.0))
    lon2 = float(loc2.get("lng", loc2.get("lon", 0.0)))

    distance = haversine_distance_meters(lat1, lon1, lat2, lon2)
    return (distance <= max_distance_meters, round(distance, 2))


def find_nearest_tanker(
    target_loc: Dict[str, Any],
    tankers: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
    """
    Find the closest tanker from a list to target_loc.
    Returns (nearest_tanker, distance_in_meters).
    """
    if not tankers:
        return None, None

    t_lat = float(target_loc.get("lat", 0.0))
    t_lon = float(target_loc.get("lng", target_loc.get("lon", 0.0)))

    nearest = None
    min_dist = float("inf")

    for tanker in tankers:
        loc = tanker.get("current_location", {})
        lat = float(loc.get("lat", 0.0))
        lon = float(loc.get("lng", loc.get("lon", 0.0)))
        dist = haversine_distance_meters(t_lat, t_lon, lat, lon)
        if dist < min_dist:
            min_dist = dist
            nearest = tanker

    return nearest, round(min_dist, 2)
