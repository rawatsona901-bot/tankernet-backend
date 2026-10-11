import pytest
from src.services.bedrock_service import (
    fallback_parse_booking_text,
    normalize_indian_numerals,
    parse_booking_text
)


def test_english_parsing():
    text = "Please deliver 6000L water to Whitefield urgently"
    result = fallback_parse_booking_text(text)
    assert result["volume"] == 6000
    assert result["location"].lower() == "whitefield"
    assert result["urgency"] == "HIGH"


def test_hindi_parsing():
    text = "मुझे 5000 लीटर पानी चाहिए साकेत में तुरंत"
    result = fallback_parse_booking_text(text)
    assert result["volume"] == 5000
    assert result["location"].lower() == "saket"
    assert result["urgency"] == "HIGH"


def test_hinglish_parsing():
    text = "Bhai 4000 liter paani chahiye Kurla urgent hai jaldi bhejo"
    result = fallback_parse_booking_text(text)
    assert result["volume"] == 4000
    assert result["location"].lower() == "kurla"
    assert result["urgency"] == "HIGH"


def test_punjabi_gurmukhi_parsing():
    # Gurmukhi Punjabi: "ਮੈਨੂੰ ਲਾਜਪਤ ਨਗਰ ਵਿੱਚ 5000 ਲੀਟਰ ਪਾਣੀ ਚਾਹੀਦਾ ਹੈ ਤੁਰੰਤ"
    text = "ਮੈਨੂੰ ਲਾਜਪਤ ਨਗਰ ਵਿੱਚ 5000 ਲੀਟਰ ਪਾਣੀ ਚਾਹੀਦਾ ਹੈ ਤੁਰੰਤ"
    result = fallback_parse_booking_text(text)
    assert result["volume"] == 5000
    assert result["location"].lower() == "lajpat nagar"
    assert result["urgency"] == "HIGH"


def test_punjabi_romanized_parsing():
    # Romanized Punjabi: "Veere 5000 litre paani chahida Saket vich, urgent hai jaldi bhejo"
    text = "Veere 5000 litre paani chahida Saket vich, urgent hai jaldi bhejo"
    result = fallback_parse_booking_text(text)
    assert result["volume"] == 5000
    assert result["location"].lower() == "saket"
    assert result["urgency"] == "HIGH"


def test_gurmukhi_numerals_normalization():
    # Gurmukhi numerals ੪੦੦੦ = 4000
    gurmukhi_num_text = "੪੦੦੦"
    normalized = normalize_indian_numerals(gurmukhi_num_text)
    assert normalized == "4000"

    text = "ਮੈਨੂੰ ੪੦੦੦ ਲੀਟਰ ਪਾਣੀ ਚਾਹੀਦਾ ਹੈ ਮਹਿਰੌਲੀ ਵਿੱਚ"
    result = fallback_parse_booking_text(text)
    assert result["volume"] == 4000
    assert result["location"].lower() == "mehrauli"


def test_low_urgency_detection():
    text = "Regular delivery of 5000L water to Indiranagar tomorrow"
    result = fallback_parse_booking_text(text)
    assert result["volume"] == 5000
    assert result["location"].lower() == "indiranagar"
    assert result["urgency"] == "LOW"
