"""AisthOS WebSocket Client — auto-reconnecting client for ESP32 or test purposes.

This module provides a resilient WebSocket client that:
- Automatically reconnects on connection loss
- Sends heartbeat pings
- Handles auth token
- Dispatches incoming display/emotion/tts commands

Used by:
- ESP32 firmware (ported to C/MicroPython)
- Test scripts
- Mobile companion app (future)
"""

import asyncio
import json
import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class AisthOSClient:
    """Auto-reconnecting WebSocket client for AisthOS server.

    Usage:
        client = AisthOSClient("ws://127.0.0.1:8765")
        client.on_display = lambda cmd: print("Display:", cmd)
        client.on_emotion = lambda emo: print("Emotion:", emo)
        client.on_tts_chunk = lambda data: play_audio(data)
        await client.connect()
        await client.send_text("Привет!")
    """

    def __init__(
        self,
        url: str = "ws://127.0.0.1:8765",
        auth_token: str = "",
        reconnect_delay: float = 3.0,
        max_reconnect_delay: float = 30.0,
        ping_interval: float = 15.0,
    ):
        self.url = url
        self.auth_token = auth_token
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.ping_interval = ping_interval

        self._ws = None
        self._connected = False
        self._running = False
        self._reconnect_attempts = 0

        # Callbacks — set these before connect()
        self.on_display: Optional[Callable] = None      # (display_cmd: dict)
        self.on_emotion: Optional[Callable] = None      # (emotion: dict)
        self.on_tts_start: Optional[Callable] = None    # (info: dict)
        self.on_tts_chunk: Optional[Callable] = None    # (audio_bytes: bytes)
        self.on_tts_end: Optional[Callable] = None      # ()
        self.on_text_response: Optional[Callable] = None  # (text: str)
        self.on_backend_info: Optional[Callable] = None   # (info: dict)
        self.on_thinking: Optional[Callable] = None       # (progress: dict)
        self.on_connected: Optional[Callable] = None      # ()
        self.on_disconnected: Optional[Callable] = None   # ()

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self):
        """Connect to server with auto-reconnect loop."""
        import websockets

        self._running = True

        while self._running:
            try:
                logger.info("Connecting to %s...", self.url)
                async with websockets.connect(
                    self.url,
                    ping_interval=None,  # We handle pings ourselves
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    self._connected = True
                    self._reconnect_attempts = 0
                    logger.info("Connected to %s", self.url)

                    # Auth if needed
                    if self.auth_token:
                        await ws.send(json.dumps({"type": "auth", "token": self.auth_token}))
                        auth_resp = await asyncio.wait_for(ws.recv(), timeout=5)
                        auth_data = json.loads(auth_resp)
                        if auth_data.get("type") != "auth_ok":
                            logger.error("Auth failed: %s", auth_data)
                            self._connected = False
                            return
                        logger.info("Authenticated")

                    # Send hello
                    await ws.send(json.dumps({"type": "hello", "version": 1}))

                    if self.on_connected:
                        self.on_connected()

                    # Start ping task
                    ping_task = asyncio.create_task(self._ping_loop())

                    # Message receive loop
                    try:
                        async for message in ws:
                            await self._handle_message(message)
                    finally:
                        ping_task.cancel()

            except Exception as e:
                logger.warning("Connection lost: %s", e)

            self._connected = False
            self._ws = None

            if self.on_disconnected:
                self.on_disconnected()

            if not self._running:
                break

            # Exponential backoff reconnect
            self._reconnect_attempts += 1
            delay = min(
                self.reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                self.max_reconnect_delay,
            )
            logger.info("Reconnecting in %.1fs (attempt %d)...", delay, self._reconnect_attempts)
            await asyncio.sleep(delay)

    async def disconnect(self):
        """Gracefully disconnect."""
        self._running = False
        if self._ws:
            await self._ws.close()

    async def send_text(self, text: str):
        """Send text message to server."""
        if self._ws and self._connected:
            await self._ws.send(json.dumps({"type": "text", "content": text}))

    async def send_touch(self, gesture: str):
        """Send touch event to server."""
        if self._ws and self._connected:
            await self._ws.send(json.dumps({"type": "touch_event", "gesture": gesture}))

    async def send_audio_start(self):
        """Signal start of audio recording."""
        if self._ws and self._connected:
            await self._ws.send(json.dumps({"type": "audio_start"}))

    async def send_audio_data(self, pcm_data: bytes):
        """Send raw PCM audio data."""
        if self._ws and self._connected:
            await self._ws.send(pcm_data)

    async def send_audio_end(self):
        """Signal end of audio recording."""
        if self._ws and self._connected:
            await self._ws.send(json.dumps({"type": "audio_end"}))

    async def send_abort(self):
        """Abort current operation."""
        if self._ws and self._connected:
            await self._ws.send(json.dumps({"type": "abort"}))

    async def _ping_loop(self):
        """Send periodic pings to keep connection alive."""
        while self._connected:
            try:
                await asyncio.sleep(self.ping_interval)
                if self._ws and self._connected:
                    await self._ws.send(json.dumps({"type": "ping", "ts": time.time()}))
            except Exception:
                break

    async def _handle_message(self, message):
        """Route incoming messages to appropriate callbacks."""
        if isinstance(message, bytes):
            # Binary = TTS audio chunk
            if self.on_tts_chunk:
                self.on_tts_chunk(message)
            return

        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")

        if msg_type == "display" and self.on_display:
            self.on_display(msg)
        elif msg_type == "emotion" and self.on_emotion:
            self.on_emotion(msg)
        elif msg_type == "tts_start" and self.on_tts_start:
            self.on_tts_start(msg)
        elif msg_type == "tts_end" and self.on_tts_end:
            self.on_tts_end()
        elif msg_type == "llm" and self.on_text_response:
            self.on_text_response(msg.get("text", ""))
        elif msg_type == "backend_info" and self.on_backend_info:
            self.on_backend_info(msg)
        elif msg_type == "thinking_progress" and self.on_thinking:
            self.on_thinking(msg)
        elif msg_type == "pong":
            pass  # Heartbeat OK
        elif msg_type == "hello":
            logger.info("Server hello: session=%s", msg.get("session_id", "?")[:8])
        elif msg_type == "error":
            logger.error("Server error: %s", msg.get("message", "unknown"))


async def test_client():
    """Quick test: connect, send greeting, print response."""
    client = AisthOSClient()

    client.on_display = lambda cmd: print(f"  🖥️  Display: {cmd.get('frame')} ({cmd.get('transition')})")
    client.on_emotion = lambda emo: print(f"  💭 Emotion: {emo.get('primary')} ({emo.get('intensity', 0):.0%})")
    client.on_text_response = lambda text: print(f"  🐱 Aisth: {text}")
    client.on_tts_start = lambda info: print(f"  🔊 TTS start (emotion: {info.get('emotion', '?')})")
    client.on_tts_end = lambda: print("  🔊 TTS end")
    client.on_backend_info = lambda info: print(f"  ⚙️  Backend: {info.get('backend')}")
    client.on_connected = lambda: print("  ✅ Connected!")
    client.on_disconnected = lambda: print("  ❌ Disconnected")

    # Connect in background
    connect_task = asyncio.create_task(client.connect())

    # Wait for connection
    for _ in range(50):
        if client.connected:
            break
        await asyncio.sleep(0.1)

    if not client.connected:
        print("Failed to connect")
        return

    # Send test message
    print("\n📤 Sending: Привет! Как дела?")
    await client.send_text("Привет! Как дела?")

    # Wait for response
    await asyncio.sleep(10)

    # Send touch
    print("\n📤 Touch: pet")
    await client.send_touch("pet")
    await asyncio.sleep(2)

    await client.disconnect()
    connect_task.cancel()


if __name__ == "__main__":
    asyncio.run(test_client())
