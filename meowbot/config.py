import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Project root = parent of meowbot/ package
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Audio
SAMPLERATE = 16000
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"

# API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# Paths
SKILLS_DIR = PROJECT_ROOT / "skills"
MEMORY_DIR = PROJECT_ROOT / "memory"

# Server
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")  # P0 Security: bind to localhost only
SERVER_PORT = int(os.getenv("SERVER_PORT", "8765"))

# TTS (edge-tts for WebSocket streaming)
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "ru-RU-DmitryNeural")
EDGE_TTS_RATE = os.getenv("EDGE_TTS_RATE", "+10%")

# WebSocket Auth (P0 Security)
WS_AUTH_TOKEN = os.getenv("WS_AUTH_TOKEN", "")  # Set in .env for production

# Emotion Recognition
EMOTION_ENABLED = os.getenv("EMOTION_ENABLED", "true").lower() == "true"
EMOTION_VOICE_BACKEND = os.getenv("EMOTION_VOICE_BACKEND", "simple")  # simple, sensevoice, sber
EMOTION_TEXT_BACKEND = os.getenv("EMOTION_TEXT_BACKEND", "claude")     # claude, gigachat, local

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
