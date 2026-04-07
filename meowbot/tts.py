"""MeowBot TTS — text-to-speech with local and streaming modes.

Local mode:  speak() — plays via macOS 'say' (for terminal)
Stream mode: generate_audio_stream() — yields MP3 chunks via edge-tts (for WebSocket)
"""

import re
import logging
import subprocess
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

# macOS voice for terminal mode
VOICE = "Milena"
RATE = 155


def clean_for_speech(text: str) -> str:
    """Strip emoji and markdown for voice output."""
    text = re.sub(r"[^\w\s,.!?;:\-\u2014\u00ab\u00bb]", "", text, flags=re.UNICODE)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def speak(text: str):
    """Speak text aloud via macOS 'say' command (terminal mode)."""
    clean = clean_for_speech(text)
    if not clean.strip():
        return
    try:
        subprocess.run(
            ["say", "-v", VOICE, "-r", str(RATE), clean],
            check=True,
            timeout=30,
        )
    except FileNotFoundError:
        logger.warning("'say' command not found — not on macOS?")
    except subprocess.TimeoutExpired:
        logger.warning("TTS timed out")
    except subprocess.CalledProcessError as e:
        logger.error("TTS failed: %s", e)


# Emotion → TTS parameters (rate and pitch adjustments)
EMOTION_TTS_PARAMS = {
    "happy":     {"rate": "+15%", "pitch": "+5Hz"},   # Faster, slightly higher
    "sad":       {"rate": "-15%", "pitch": "-5Hz"},   # Slower, lower
    "angry":     {"rate": "+10%", "pitch": "+0Hz"},   # Faster, normal pitch
    "surprised": {"rate": "+5%",  "pitch": "+10Hz"},  # Slightly faster, higher
    "fear":      {"rate": "-10%", "pitch": "+5Hz"},   # Slower, slightly higher
    "neutral":   {"rate": "+0%",  "pitch": "+0Hz"},   # Default
}


async def generate_audio_stream(text: str, emotion: str = "neutral") -> AsyncGenerator[bytes]:
    """Yield MP3 audio chunks from text via edge-tts (for WebSocket streaming).

    Args:
        text: Text to speak
        emotion: Emotion name to adjust voice parameters (happy, sad, etc.)
    """
    import edge_tts
    from meowbot.config import EDGE_TTS_VOICE, EDGE_TTS_RATE

    clean = clean_for_speech(text)
    if not clean.strip():
        return

    # Apply emotion-based voice adjustments
    emo_params = EMOTION_TTS_PARAMS.get(emotion, EMOTION_TTS_PARAMS["neutral"])

    # Combine base rate with emotion adjustment
    # Base rate is like "+10%", emotion rate is like "+15%"
    # For simplicity, use emotion rate directly if emotion is not neutral
    rate = emo_params["rate"] if emotion != "neutral" else EDGE_TTS_RATE
    pitch = emo_params.get("pitch", "+0Hz")

    logger.debug("TTS emotion=%s, rate=%s, pitch=%s", emotion, rate, pitch)

    communicate = edge_tts.Communicate(
        clean,
        voice=EDGE_TTS_VOICE,
        rate=rate,
        pitch=pitch,
    )
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]
