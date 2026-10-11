#!/usr/bin/env python3
"""
TankerNet - Tanker Telemetry Simulator
Simulates a water tanker driving along the Saket -> Lajpat Nagar route in Delhi.
Transmits GPS coordinates, fluctuating TDS (with an intentional contamination spike
and subsequent clean water recovery), and triggers automatic valve locking.
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

# Ensure src is on python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set default offline test environment variables
os.environ.setdefault("MOCK_DYNAMODB", "true")
os.environ.setdefault("USE_LOCAL_PARSER", "true")
os.environ.setdefault("MOCK_IOT", "true")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")

from src.utils.geo import haversine_distance_meters

# Geocoded reference coordinates for Lajpat Nagar: (28.5677, 77.2433)
LAJPAT_NAGAR_REF = {"lat": 28.5677, "lng": 77.2433}

# Saket -> Lajpat Nagar Route Waypoints
# Final point is within ~3 meters of Lajpat Nagar reference coordinates (strictly <= 20m)
ROUTE_WAYPOINTS = [
    {
        "name": "Saket Departure Depot",
        "lat": 28.5244,
        "lng": 77.2066,
        "tds": 380,
        "turbidity": 1.4,
        "phase": "Baseline departure - normal water quality"
    },
    {
        "name": "Pushp Vihar Sector 4",
        "lat": 28.5360,
        "lng": 77.2185,
        "tds": 395,
        "turbidity": 1.6,
        "phase": "Transit underway - water within limits"
    },
    {
        "name": "Chirag Dilli Flyover (Contamination Event)",
        "lat": 28.5470,
        "lng": 77.2290,
        "tds": 555,  # Contamination spike (>500 ppm) -> Triggers FLAGGED & Valve Lock
        "turbidity": 5.8,  # High turbidity (>5 NTU)
        "phase": "SPIKE DETECTED: TDS > 500, Turbidity > 5.0 -> FLAGGED & Valve Locked!"
    },
    {
        "name": "Andrews Ganj Intersection (Recovery Phase)",
        "lat": 28.5580,
        "lng": 77.2370,
        "tds": 385,  # Normalized (350-420 ppm) -> Clears FLAGGED to IN_TRANSIT
        "turbidity": 1.8,
        "phase": "RECOVERY: Water filtered/flushed (TDS 385 ppm) -> Cleared to IN_TRANSIT (Valve remains locked)"
    },
    {
        "name": "Lajpat Nagar Delivery Point (Arrival)",
        # Offset by ~3.5 meters from target (28.5677, 77.2433)
        "lat": 28.56772,
        "lng": 77.24332,
        "tds": 375,  # Within 350-420 ppm
        "turbidity": 1.5,
        "phase": "ARRIVED: Within 20m geofence of customer location. Ready for OTP unlock."
    }
]


def send_telemetry_http(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send telemetry via HTTP POST."""
    import urllib.request
    import urllib.error

    url = endpoint if endpoint.endswith("/api/tanker/telemetry") else f"{endpoint.rstrip('/')}/api/tanker/telemetry"
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_telemetry_internal(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke local Python handler directly (for offline/test mode)."""
    from src.handlers.telemetry_handler import handler
    event = {"body": json.dumps(payload)}
    resp = handler(event)
    return json.loads(resp["body"])


def send_telemetry_mqtt(topic: str, payload: Dict[str, Any], iot_endpoint: str) -> None:
    """Publish telemetry directly to AWS IoT Core MQTT topic."""
    import boto3
    endpoint_url = iot_endpoint if iot_endpoint.startswith("https://") else f"https://{iot_endpoint}"
    client = boto3.client("iot-data", endpoint_url=endpoint_url)
    client.publish(
        topic=topic,
        qos=1,
        payload=json.dumps(payload)
    )


def run_simulation(
    tanker_id: str = "TANKER-DEL-01",
    mode: str = "internal",
    endpoint: str = "http://127.0.0.1:3000",
    interval: float = 1.0,
    dry_run: bool = False
):
    print("=" * 75)
    print("   TANKERNET ROUTE SIMULATOR: SAKET -> LAJPAT NAGAR (DELHI)   ")
    print("=" * 75)
    print(f"Tanker ID:   {tanker_id}")
    print(f"Mode:        {mode}")
    print(f"Destination: Lajpat Nagar ({LAJPAT_NAGAR_REF['lat']}, {LAJPAT_NAGAR_REF['lng']})")
    print(f"Waypoints:   {len(ROUTE_WAYPOINTS)}")
    print("-" * 75)

    final_wp = ROUTE_WAYPOINTS[-1]
    final_dist = haversine_distance_meters(
        final_wp["lat"], final_wp["lng"],
        LAJPAT_NAGAR_REF["lat"], LAJPAT_NAGAR_REF["lng"]
    )
    print(f"Final waypoint distance to Lajpat Nagar target: {final_dist:.2f} meters (Geofence threshold <= 20m)")
    assert final_dist <= 20.0, f"Final waypoint {final_dist}m exceeds 20m threshold!"
    print("-" * 75)

    for i, wp in enumerate(ROUTE_WAYPOINTS, start=1):
        payload = {
            "tanker_id": tanker_id,
            "lat": wp["lat"],
            "lng": wp["lng"],
            "tds": wp["tds"],
            "turbidity": wp["turbidity"],
            "waypoint_name": wp["name"]
        }

        print(f"\n[Step {i}/{len(ROUTE_WAYPOINTS)}] {wp['name']}")
        print(f"  Coordinates: ({wp['lat']:.5f}, {wp['lng']:.5f})")
        print(f"  Water Quality: TDS={wp['tds']} ppm | Turbidity={wp['turbidity']} NTU")
        print(f"  Simulation Phase: {wp['phase']}")

        if dry_run:
            print("  [DRY RUN] Payload:", json.dumps(payload))
        else:
            try:
                if mode == "http":
                    result = send_telemetry_http(endpoint, payload)
                elif mode == "mqtt":
                    iot_endpoint = os.environ.get("IOT_ENDPOINT", "localhost")
                    send_telemetry_mqtt(f"tanker/{tanker_id}/telemetry", payload, iot_endpoint)
                    result = {"status": "PUBLISHED_MQTT", "topic": f"tanker/{tanker_id}/telemetry"}
                else:  # internal direct handler
                    result = send_telemetry_internal(payload)

                print(f"  Response Status:  {result.get('status', 'OK')}")
                print(f"  Valve Locked:     {result.get('valve_locked')}")
                if result.get("status") == "FLAGGED":
                    print("  >>> [SAFETY ALERT] Contamination detected! Valve has been automatically locked.")
                elif wp["tds"] <= 500 and result.get("valve_locked"):
                    print("  >>> [RECOVERY] Water normalized. Valve safely remains locked awaiting customer OTP.")
            except Exception as exc:
                print(f"  Error transmitting telemetry: {exc}")

        if i < len(ROUTE_WAYPOINTS) and interval > 0:
            time.sleep(interval)

    print("\n" + "=" * 75)
    print("Simulation complete! Tanker is positioned at Lajpat Nagar ready for unlock.")
    print("=" * 75)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TankerNet GPS and Quality Telemetry Simulator")
    parser.add_argument("--tanker-id", default="TANKER-DEL-01", help="Tanker ID to simulate (default: TANKER-DEL-01)")
    parser.add_argument("--mode", choices=["internal", "http", "mqtt"], default="internal",
                        help="Dispatch mode: internal (direct handler), http (API Gateway), mqtt (AWS IoT Core)")
    parser.add_argument("--endpoint", default="http://127.0.0.1:3000", help="HTTP API Gateway base endpoint")
    parser.add_argument("--interval", type=float, default=1.0, help="Delay between waypoints in seconds (default: 1.0)")
    parser.add_argument("--dry-run", action="store_true", help="Print telemetry payloads without dispatching")
    args = parser.parse_args()

    run_simulation(
        tanker_id=args.tanker_id,
        mode=args.mode,
        endpoint=args.endpoint,
        interval=args.interval,
        dry_run=args.dry_run
    )
