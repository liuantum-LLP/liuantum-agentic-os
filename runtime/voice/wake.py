from __future__ import annotations

import re

def normalize_wake_phrase(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text)
    # Normalize spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def detect_wake_phrase(transcript: str, wake_phrases: list[str]) -> dict:
    if not transcript:
        return {
            "woke": False,
            "matched_phrase": None,
            "command_text": "",
            "confidence": 0.0
        }
        
    norm_transcript = normalize_wake_phrase(transcript)
    best_match_phrase = None
    best_match_norm = None
    best_len = 0
    
    for phrase in wake_phrases:
        norm_phrase = normalize_wake_phrase(phrase)
        if not norm_phrase:
            continue
        if norm_transcript == norm_phrase or norm_transcript.startswith(norm_phrase + " "):
            if len(norm_phrase) > best_len:
                best_match_phrase = phrase
                best_match_norm = norm_phrase
                best_len = len(norm_phrase)
                
    if best_match_phrase:
        words = best_match_norm.split()
        regex_parts = [re.escape(w) for w in words]
        # Match at the start of transcript, allowing punctuation and spaces
        pattern_str = r"^\s*" + r"\s*[^\w\s]*\s*".join(regex_parts) + r"\s*[^\w\s]*\s*"
        match = re.match(pattern_str, transcript, re.IGNORECASE)
        if match:
            remainder = transcript[match.end():].strip()
        else:
            remainder = transcript[len(best_match_phrase):].strip()
            
        # Clean up remainder
        remainder = re.sub(r"^[,\-\s:]+", "", remainder).strip()
        
        return {
            "woke": True,
            "matched_phrase": best_match_phrase.lower(),
            "command_text": remainder,
            "confidence": 0.95
        }
        
    return {
        "woke": False,
        "matched_phrase": None,
        "command_text": "",
        "confidence": 0.0
    }

def should_wake(transcript: str, settings: dict) -> bool:
    if not settings.get("voice_enabled") or not settings.get("wake_listening_enabled"):
        return False
    res = detect_wake_phrase(transcript, settings.get("wake_phrases", []))
    return res["woke"]

def wake_response(settings: dict) -> str:
    # Just returns the configured response greeting
    return settings.get("wake_response", "Yes, what do you want?")
