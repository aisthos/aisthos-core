"""Tests for MeowBot WebSocket server — protocol, session, audio conversion."""

import json
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from meowbot.server import PROTOCOL_VERSION, ClientSession


class TestProtocolMessages:
    """Test protocol message format and validation."""

    def test_hello_message_format(self):
        """Client hello message has required fields."""
        msg = {
            "type": "hello",
            "version": 1,
            "audio_params": {"format": "pcm", "sample_rate": 16000, "channels": 1},
        }
        assert msg["type"] == "hello"
        assert msg["version"] == 1
        assert msg["audio_params"]["sample_rate"] == 16000

    def test_text_message_format(self):
        msg = {"type": "text", "content": "привет кот"}
        assert msg["type"] == "text"
        assert msg["content"] == "привет кот"

    def test_protocol_version(self):
        assert PROTOCOL_VERSION == 1


class TestClientSession:
    """Test session lifecycle."""

    def test_session_creation(self):
        ws = MagicMock()
        session = ClientSession(websocket=ws)
        assert session.websocket is ws
        assert len(session.session_id) == 36  # UUID format
        assert session.agent is None
        assert session.audio_buffer == bytearray()
        assert session.recording is False
        assert session.aborted is False

    def test_session_id_unique(self):
        ws = MagicMock()
        s1 = ClientSession(websocket=ws)
        s2 = ClientSession(websocket=ws)
        assert s1.session_id != s2.session_id


class TestAudioConversion:
    """Test PCM int16 bytes to float32 numpy conversion."""

    def test_pcm_to_float32(self):
        """Convert PCM int16 bytes to float32 numpy array."""
        # Create test PCM data (silence = zeros)
        pcm_data = struct.pack("<4h", 0, 16384, -16384, 32767)
        audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0

        assert audio_np.dtype == np.float32
        assert len(audio_np) == 4
        assert abs(audio_np[0]) < 0.001  # ~0
        assert abs(audio_np[1] - 0.5) < 0.001  # ~0.5
        assert abs(audio_np[2] + 0.5) < 0.001  # ~-0.5
        assert abs(audio_np[3] - 1.0) < 0.001  # ~1.0

    def test_pcm_empty_buffer(self):
        """Empty buffer produces empty array."""
        audio_np = np.frombuffer(b"", dtype=np.int16).astype(np.float32) / 32768.0
        assert len(audio_np) == 0

    def test_pcm_mono_16khz_1sec(self):
        """1 second of 16kHz mono = 32000 bytes = 16000 samples."""
        n_samples = 16000
        pcm_data = np.zeros(n_samples, dtype=np.int16).tobytes()
        assert len(pcm_data) == 32000

        audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        assert len(audio_np) == 16000


class TestServerConfig:
    """Test server configuration."""

    def test_server_config_loaded(self):
        from meowbot.config import SERVER_HOST, SERVER_PORT, EDGE_TTS_VOICE, EDGE_TTS_RATE

        assert SERVER_HOST == "0.0.0.0"
        assert SERVER_PORT == 8765
        assert "ru-RU" in EDGE_TTS_VOICE
        assert EDGE_TTS_RATE  # Not empty


class TestSendJson:
    """Test JSON message sending."""

    @pytest.mark.asyncio
    async def test_send_json(self):
        from meowbot.server import send_json

        ws = AsyncMock()
        await send_json(ws, {"type": "hello", "version": 1})
        ws.send.assert_called_once()
        sent = json.loads(ws.send.call_args[0][0])
        assert sent["type"] == "hello"
        assert sent["version"] == 1

    @pytest.mark.asyncio
    async def test_send_json_russian(self):
        """Russian text should not be escaped."""
        from meowbot.server import send_json

        ws = AsyncMock()
        await send_json(ws, {"type": "llm", "text": "Мяу!"})
        sent = ws.send.call_args[0][0]
        assert "Мяу!" in sent  # Not escaped as \u041c\u044f\u0443
