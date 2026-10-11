import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def publish_valve_unlock(tanker_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Publish valve unlock instruction to AWS IoT topic tanker/{tanker_id}/valve.
    Handles offline/mock execution when IoT endpoint is unavailable or during local testing.
    """
    topic = f"tanker/{tanker_id}/valve"
    iot_endpoint = os.environ.get("IOT_ENDPOINT")

    # If running locally or without credentials/endpoint, log and succeed gracefully
    if not iot_endpoint or os.environ.get("MOCK_IOT", "false").lower() in ["true", "1", "yes"]:
        logger.info("[OFFLINE/MOCK IoT] Published to topic '%s': %s", topic, json.dumps(payload))
        return {
            "status": "MOCK_PUBLISHED",
            "topic": topic,
            "payload": payload
        }

    try:
        import boto3
        # Ensure endpoint has https scheme or strip if needed
        endpoint_url = iot_endpoint if iot_endpoint.startswith("https://") else f"https://{iot_endpoint}"
        client = boto3.client("iot-data", endpoint_url=endpoint_url)

        client.publish(
            topic=topic,
            qos=1,
            payload=json.dumps(payload)
        )
        logger.info("Successfully published unlock command to IoT topic '%s'", topic)
        return {
            "status": "PUBLISHED",
            "topic": topic,
            "payload": payload
        }
    except Exception as exc:
        logger.warning("Could not publish to AWS IoT Core (%s). Falling back gracefully.", exc)
        return {
            "status": "FALLBACK_LOGGED",
            "topic": topic,
            "payload": payload,
            "warning": str(exc)
        }
