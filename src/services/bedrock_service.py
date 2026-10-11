import json
import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Default Bedrock Model ID
DEFAULT_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

# Gurmukhi and Devanagari digit converters
GURMUKHI_DIGITS = {"੦": "0", "੧": "1", "੨": "2", "੩": "3", "੪": "4", "੫": "5", "੬": "6", "੭": "7", "੮": "8", "੯": "9"}
DEVANAGARI_DIGITS = {"०": "0", "१": "1", "२": "2", "३": "3", "४": "4", "५": "5", "६": "6", "७": "7", "८": "8", "९": "9"}


def normalize_indian_numerals(text: str) -> str:
    """Convert Gurmukhi and Devanagari numerals to standard ASCII digits."""
    for g_char, ascii_digit in GURMUKHI_DIGITS.items():
        text = text.replace(g_char, ascii_digit)
    for d_char, ascii_digit in DEVANAGARI_DIGITS.items():
        text = text.replace(d_char, ascii_digit)
    return text


def fallback_parse_booking_text(text: str) -> Dict[str, Any]:
    """
    Deterministic rule-based NLP fallback parser.
    Supports English, Hindi, Hinglish, and Punjabi (Gurmukhi & Romanized).
    Extracts volume (in liters), location, and urgency (HIGH, MEDIUM, LOW).
    """
    if not text:
        return {"volume": 5000, "location": "Saket", "urgency": "MEDIUM"}

    normalized_text = normalize_indian_numerals(text)
    lower_text = normalized_text.lower()

    # 1. VOLUME EXTRACTION
    volume = 5000  # standard default tanker volume
    vol_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(k|kilo|thousand)?\s*(?:l|ltr|liter|liters|litre|litres|लीटर|ਲੀਟਰ)?(?:\b|\s|$)",
        lower_text
    )
    if vol_match:
        val = float(vol_match.group(1))
        unit_mult = vol_match.group(2)
        if unit_mult in ["k", "kilo", "thousand"] or val < 50:
            volume = int(val * 1000)
        else:
            volume = int(val)

    # 2. URGENCY EXTRACTION
    # Gurmukhi markers: ਤੁਰੰਤ, ਜਲਦੀ, ਛੇਤੀ, ਐਮਰਜੈਂਸੀ, ਜ਼ਰੂਰੀ
    # Hindi/Hinglish markers: urgent, turant, jaldi, abhi, emergency, jaldi se
    # English markers: asap, emergency, urgent, urgently, critical, immediately
    high_urgency_patterns = [
        r"\b(?:urgent|urgently|asap|emergency|critical|immediately)\b",
        r"\b(?:turant|jaldi|abhi|fatafat|zaroori)\b",
        r"(?:ਤੁਰੰਤ|ਜਲਦੀ|ਛੇਤੀ|ਐਮਰਜੈਂਸੀ|ਜ਼ਰੂਰੀ)",
        r"(?:तुरंत|जल्दी|अभी|आपातकालीन)"
    ]
    low_urgency_patterns = [
        r"\b(?:standard|regular|low|later|aaram se|halke)\b",
        r"(?:ਹੌਲੀ|ਬਾਅਦ|ਆਰਾਮ)",
        r"(?:बाद में|आराम से)"
    ]

    urgency = "MEDIUM"
    for pattern in high_urgency_patterns:
        if re.search(pattern, lower_text):
            urgency = "HIGH"
            break

    if urgency != "HIGH":
        for pattern in low_urgency_patterns:
            if re.search(pattern, lower_text):
                urgency = "LOW"
                break

    # 3. LOCATION EXTRACTION
    # Location keywords mapping across English, Hindi, Punjabi
    location_candidates = [
        # Delhi
        ("dwarka sec 10", [r"dwarka\s*(?:sec(?:tor)?\s*10)?", r"ਦਵਾਰਕਾ", r"द्वारका"]),
        ("saket", [r"saket", r"ਸਾਕੇਤ", r"साकेत"]),
        ("lajpat nagar", [r"lajpat(?:\s*nagar)?", r"ਲਾਜਪਤ(?:\s*ਨਗਰ)?", r"लाजपत(?:\s*नगर)?"]),
        ("mehrauli", [r"mehrauli", r"ਮਹਿਰੌਲੀ", r"महरौली"]),

        # Mumbai
        ("mankhurd", [r"mankhurd", r"ਮਾਨਖੁਰਦ", r"मानखुर्द"]),
        ("govandi", [r"govandi", r"ਗੋਵੰਡੀ", r"गोवंडी"]),
        ("kurla", [r"kurla", r"ਕੁਰਲਾ", r"कुर्ला"]),
        ("andheri east", [r"andheri(?:\s*east)?", r"ਅੰਧੇਰੀ(?:\s*ਈਸਟ)?", r"अंधेरी(?:\s*ईस्ट)?"]),

        # Bengaluru
        ("whitefield", [r"whitefield", r"ਵ੍ਹਾਈਟਫੀਲਡ", r"व्हाइटफ़ील्ड"]),
        ("bellandur", [r"bellandur", r"ਬੇਲੰਦੁਰ", r"बेलंदूर"]),
        ("koramangala", [r"koramangala", r"ਕੋਰਮੰਗਲਾ", r"कोरमंगला"]),
        ("indiranagar", [r"indiranagar", r"indira\s*nagar", r"ਇੰਦਰਾ\s*ਨਗਰ", r"इंदिरानगर"])
    ]

    detected_location = None
    for canonical_name, patterns in location_candidates:
        for pat in patterns:
            if re.search(pat, lower_text):
                detected_location = canonical_name
                break
        if detected_location:
            break

    # If no specific recognized candidate found, try to extract words after prepositions like 'at', 'in', 'par', 'vich'
    if not detected_location:
        loc_prep_match = re.search(r"(?:at|in|near|to|par|pe|vich|ਵਿੱਚ|ਤੇ|पर|में)\s+([a-zA-Z\u0900-\u097F\u0A00-\u0A7F\s]{3,20})", text, re.IGNORECASE)
        if loc_prep_match:
            candidate = loc_prep_match.group(1).strip()
            # Clean up trailing words like 'urgent', 'chahida', 'hai'
            candidate = re.sub(r"\b(?:urgent|chahida|hai|vich|turant|jaldi|please)\b", "", candidate, flags=re.IGNORECASE).strip()
            if candidate:
                detected_location = candidate

    if not detected_location:
        detected_location = "Saket"  # Safe default within 3-city scope

    return {
        "volume": volume,
        "location": detected_location,
        "urgency": urgency
    }


def parse_booking_text(text: str) -> Dict[str, Any]:
    """
    Parse free-text booking query using Amazon Bedrock with automatic local fallback.
    Extracts {volume: int, location: str, urgency: str}.
    """
    use_local_parser = os.environ.get("USE_LOCAL_PARSER", "false").lower() in ["true", "1", "yes"]
    if use_local_parser:
        return fallback_parse_booking_text(text)

    # Attempt Bedrock LLM invocation
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        client = boto3.client("bedrock-runtime")

        prompt = f"""You are an AI assistant for TankerNet, a water tanker delivery system.
Extract the delivery details from the following user request written in Hindi, English, Hinglish, or Punjabi.
Return ONLY a valid JSON object with the following schema:
{{
  "volume": <integer in liters, default 5000 if not specified>,
  "location": "<canonical city location name, e.g. Saket, Lajpat Nagar, Indiranagar, Kurla>",
  "urgency": "<HIGH|MEDIUM|LOW>"
}}

User Request: "{text}"

JSON:"""

        # Using Claude / Titan JSON format
        model_id = os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)

        if "anthropic.claude" in model_id:
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "temperature": 0.0,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        else:
            # Amazon Titan fallback payload format
            payload = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 200,
                    "temperature": 0.0,
                    "topP": 0.9
                }
            }

        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload)
        )

        response_body = json.loads(response["body"].read().decode("utf-8"))

        if "anthropic.claude" in model_id:
            raw_text = response_body["content"][0]["text"]
        elif "results" in response_body:
            raw_text = response_body["results"][0]["outputText"]
        else:
            raw_text = str(response_body)

        # Parse JSON from model output
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            return {
                "volume": int(parsed.get("volume", 5000)),
                "location": str(parsed.get("location", "Saket")),
                "urgency": str(parsed.get("urgency", "MEDIUM")).upper()
            }
    except Exception as exc:
        logger.warning("Bedrock invocation unavailable or failed (%s). Using local fallback parser.", exc)

    # Fallback to local rule-based NLP parser
    return fallback_parse_booking_text(text)
