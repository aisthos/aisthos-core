import logging
import tempfile

import numpy as np
import scipy.io.wavfile as wav

from meowbot.config import SAMPLERATE, WHISPER_MODEL

logger = logging.getLogger(__name__)

# Lazy-loaded VAD model
_vad_model = None

WHISPER_HALLUCINATIONS = [
    "продолжение следует", "continue", "subtitles by",
    "субтитры", "переведено", "translation", "thank you",
]


def _ensure_vad():
    """Load Silero VAD on first use."""
    global _vad_model
    if _vad_model is not None:
        return
    import torch
    logger.info("Loading Silero VAD model...")
    _vad_model, _ = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        trust_repo=True,
    )
    logger.info("Silero VAD ready.")


def warmup():
    """Pre-run Whisper on silence so first real transcription is fast."""
    import mlx_whisper

    logger.info("Warming up Whisper model...")
    silence = np.zeros(SAMPLERATE, dtype=np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav.write(f.name, SAMPLERATE, silence)
        mlx_whisper.transcribe(f.name, path_or_hf_repo=WHISPER_MODEL, language="ru")
    logger.info("Whisper warm-up complete.")


def record_with_vad(max_seconds: int = 10, silence_seconds: float = 1.5) -> np.ndarray:
    """Record audio from microphone, stop automatically when speech ends."""
    import torch
    import sounddevice as sd

    _ensure_vad()

    logger.info("Listening...")
    chunk_size = 512
    recorded = []
    speech_started = False
    silence_chunks = 0
    silence_limit = int(silence_seconds / (chunk_size / SAMPLERATE))

    with sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype="float32") as stream:
        for _ in range(int(max_seconds * SAMPLERATE / chunk_size)):
            chunk, _ = stream.read(chunk_size)
            chunk_flat = chunk.flatten()
            recorded.append(chunk_flat)

            tensor = torch.from_numpy(chunk_flat)
            speech_prob = _vad_model(tensor, SAMPLERATE).item()

            if speech_prob > 0.5:
                speech_started = True
                silence_chunks = 0
            elif speech_started:
                silence_chunks += 1
                if silence_chunks >= silence_limit:
                    break

    return np.concatenate(recorded)


def transcribe(audio: np.ndarray) -> str:
    """Transcribe audio array to text using Whisper."""
    import mlx_whisper

    if np.abs(audio).max() < 0.02:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav.write(f.name, SAMPLERATE, (audio * 32768).astype(np.int16))
        result = mlx_whisper.transcribe(
            f.name,
            path_or_hf_repo=WHISPER_MODEL,
            language="ru",
            no_speech_threshold=0.6,
            condition_on_previous_text=False,
        )
        text = result["text"].strip()

        if any(h in text.lower() for h in WHISPER_HALLUCINATIONS):
            return ""

        return text
