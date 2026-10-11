import re
from typing import Dict, Any, Optional, Tuple


GEOCODE_LOCATIONS = {
    # Delhi
    "dwarka sec 10": {"lat": 28.5823, "lng": 77.0587, "city": "Delhi", "display_name": "Dwarka Sec 10"},
    "saket": {"lat": 28.5244, "lng": 77.2066, "city": "Delhi", "display_name": "Saket"},
    "lajpat nagar": {"lat": 28.5677, "lng": 77.2433, "city": "Delhi", "display_name": "Lajpat Nagar"},
    "mehrauli": {"lat": 28.5175, "lng": 77.1824, "city": "Delhi", "display_name": "Mehrauli"},

    # Mumbai
    "mankhurd": {"lat": 19.0494, "lng": 72.9315, "city": "Mumbai", "display_name": "Mankhurd"},
    "govandi": {"lat": 19.0560, "lng": 72.9158, "city": "Mumbai", "display_name": "Govandi"},
    "kurla": {"lat": 19.0726, "lng": 72.8845, "city": "Mumbai", "display_name": "Kurla"},
    "andheri east": {"lat": 19.1136, "lng": 72.8697, "city": "Mumbai", "display_name": "Andheri East"},

    # Bengaluru
    "whitefield": {"lat": 12.9698, "lng": 77.7500, "city": "Bengaluru", "display_name": "Whitefield"},
    "bellandur": {"lat": 12.9304, "lng": 77.6784, "city": "Bengaluru", "display_name": "Bellandur"},
    "koramangala": {"lat": 12.9352, "lng": 77.6245, "city": "Bengaluru", "display_name": "Koramangala"},
    "indiranagar": {"lat": 12.9719, "lng": 77.6412, "city": "Bengaluru", "display_name": "Indiranagar"},
}

# Alias mapping including partial names, Hindi and Punjabi (Gurmukhi) scripts
LOCATION_ALIASES = {
    # Delhi
    "dwarka": "dwarka sec 10",
    "dwarka sector 10": "dwarka sec 10",
    "द्वारका": "dwarka sec 10",
    "द्वारका सेक्टर 10": "dwarka sec 10",
    "ਦਵਾਰਕਾ": "dwarka sec 10",
    "ਦਵਾਰਕਾ ਸੈਕਟਰ 10": "dwarka sec 10",

    "साकेत": "saket",
    "ਸਾਕੇਤ": "saket",

    "lajpat": "lajpat nagar",
    "लाजपत नगर": "lajpat nagar",
    "ਲਾਜਪਤ ਨਗਰ": "lajpat nagar",
    "ਲਾਜਪਤ": "lajpat nagar",

    "महरौली": "mehrauli",
    "ਮਹਿਰੌਲੀ": "mehrauli",

    # Mumbai
    "मानखुर्द": "mankhurd",
    "ਮਾਨਖੁਰਦ": "mankhurd",

    "गोवंडी": "govandi",
    "ਗੋਵੰਡੀ": "govandi",

    "कुर्ला": "kurla",
    "ਕੁਰਲਾ": "kurla",

    "andheri": "andheri east",
    "अंधेरी ईस्ट": "andheri east",
    "अंधेरी": "andheri east",
    "ਅੰਧੇਰੀ ਈਸਟ": "andheri east",
    "ਅੰਧੇਰੀ": "andheri east",

    # Bengaluru
    "व्हाइटफ़ील्ड": "whitefield",
    "ਵ੍ਹਾਈਟਫੀਲਡ": "whitefield",
    "ਵ੍ਹਾਈਟਫੀਲ਼ਡ": "whitefield",

    "बेलंदूर": "bellandur",
    "ਬੇਲੰਦੁਰ": "bellandur",

    "कोरमंगला": "koramangala",
    "ਕੋਰਮੰਗਲਾ": "koramangala",

    "indira nagar": "indiranagar",
    "इंदिरानगर": "indiranagar",
    "इंद्रा नगर": "indiranagar",
    "ਇੰਦਰਾ ਨਗਰ": "indiranagar",
    "ਇੰਦਿਰਾਨਗਰ": "indiranagar",
}


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and stripping punctuation/extra spaces."""
    cleaned = re.sub(r"[^\w\s\u0900-\u097F\u0A00-\u0A7F]", " ", text.lower())
    return " ".join(cleaned.split())


def geocode_location(query: str) -> Optional[Dict[str, Any]]:
    """
    Geocode a query to coordinates, city, and display name using the 3-city lookup dictionary.
    Returns dict with keys: lat, lng, city, display_name or None if not found.
    """
    if not query:
        return None

    normalized = normalize_text(query)

    # 1. Direct match in canonical dictionary
    if normalized in GEOCODE_LOCATIONS:
        return dict(GEOCODE_LOCATIONS[normalized])

    # 2. Match in aliases
    if normalized in LOCATION_ALIASES:
        canonical_key = LOCATION_ALIASES[normalized]
        return dict(GEOCODE_LOCATIONS[canonical_key])

    # 3. Substring match against canonical keys and aliases
    # Sort by length descending to match multi-word entries first (e.g. "Dwarka Sec 10" before "Dwarka")
    all_keys = sorted(
        list(GEOCODE_LOCATIONS.keys()) + list(LOCATION_ALIASES.keys()),
        key=lambda x: len(x),
        reverse=True
    )
    for key in all_keys:
        if key in normalized:
            canonical_key = LOCATION_ALIASES.get(key, key)
            return dict(GEOCODE_LOCATIONS[canonical_key])

    return None
