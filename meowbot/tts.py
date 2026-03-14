import re
import logging

import pyttsx3

logger = logging.getLogger(__name__)

_engine = None


def _get_engine():
    """Get or create the TTS engine (singleton)."""
    global _engine
    if _engine is None:
        logger.info("Initializing TTS engine...")
        _engine = pyttsx3.init()
        for v in _engine.getProperty("voices"):
            if "milena" in v.name.lower() or "milena" in v.id.lower():
                _engine.setProperty("voice", v.id)
                logger.info("TTS voice: %s", v.name)
                break
        _engine.setProperty("rate", 155)
    return _engine


def clean_for_speech(text: str) -> str:
    """Strip emoji and markdown for voice output."""
    text = re.sub(r"[^\w\s,.!?;:\-\u2014\u00ab\u00bb]", "", text, flags=re.UNICODE)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def speak(text: str):
    """Speak text aloud via pyttsx3."""
    clean = clean_for_speech(text)
    if not clean.strip():
        return
    engine = _get_engine()
    engine.say(clean)
    engine.runAndWait()
