"""MeowBot WebSocket Server — bridge between ESP32/browser and AI brain.

Protocol:
  Text frames  → JSON control messages (hello, text, audio_start/end, abort)
  Binary frames → PCM int16 16kHz mono audio data (client→server)
                  MP3 audio chunks (server→client)

Run: python -m meowbot.server
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import numpy as np
import websockets

from meowbot.config import SERVER_HOST, SERVER_PORT, WS_AUTH_TOKEN
from meowbot.display_agent import DisplayAgent
from meowbot.llm_backend import BackendType
from meowbot.tts import generate_audio_stream

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1


@dataclass
class ClientSession:
    """State for a connected client."""
    websocket: object
    session_id: str = field(default_factory=lambda: str(uuid4()))
    agent: object = None  # MeowBotAgent, created on hello
    display: DisplayAgent = field(default_factory=DisplayAgent)
    audio_buffer: bytearray = field(default_factory=bytearray)
    recording: bool = False
    aborted: bool = False


async def send_json(ws, data: dict):
    """Send a JSON text frame."""
    await ws.send(json.dumps(data, ensure_ascii=False))


SKILLS_DIR = Path(__file__).parent.parent / "skills"

# ── Skill icons (emoji) by tag/name ──
SKILL_ICONS = {
    "emotion": "🎭", "empathy": "🎭",
    "search": "🔍", "internet": "🔍",
    "story": "📖", "fairy-tale": "📖",
    "reminder": "⏰", "productivity": "⏰",
    "smart-home": "🏠", "home": "🏠",
}

SKILL_CATEGORIES = {
    "emotion": "core", "empathy": "core",
    "search": "productivity", "internet": "productivity",
    "reminder": "productivity", "productivity": "productivity",
    "story": "entertainment", "fairy-tale": "entertainment", "kids": "entertainment",
    "smart-home": "smart_home", "home": "smart_home",
}


def _parse_skill_frontmatter(skill_path: Path) -> dict | None:
    """Parse YAML frontmatter from SKILL.md file."""
    md_file = skill_path / "SKILL.md"
    if not md_file.exists():
        return None
    text = md_file.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    # Simple YAML parser for our frontmatter (no PyYAML dependency)
    data = {"id": skill_path.name, "path": str(skill_path)}
    for line in m.group(1).split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key, val = key.strip(), val.strip()
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
            elif val in ("true", "True"):
                val = True
            elif val in ("false", "False"):
                val = False
            data[key] = val
    # Add icon and category from tags
    tags = data.get("tags", [])
    icon = "🔧"
    category = "other"
    for tag in (tags if isinstance(tags, list) else []):
        if tag in SKILL_ICONS:
            icon = SKILL_ICONS[tag]
        if tag in SKILL_CATEGORIES:
            category = SKILL_CATEGORIES[tag]
    data["icon"] = icon
    data["category"] = category
    return data


def scan_skills() -> list[dict]:
    """Scan skills/ directory and return metadata for all skills."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    for entry in sorted(SKILLS_DIR.iterdir()):
        if entry.is_dir() and (entry / "SKILL.md").exists():
            info = _parse_skill_frontmatter(entry)
            if info:
                skills.append(info)
    return skills


async def handle_hello(session: ClientSession, msg: dict):
    """Handle hello handshake — create agent for this session."""
    from meowbot.audio_agent import MeowBotAgent

    logger.info("Client hello from %s", session.session_id[:8])

    # Create agent in thread (heavy: loads embeddings, ChromaDB)
    session.agent = await asyncio.to_thread(MeowBotAgent, user_id="vladimir")

    await send_json(session.websocket, {
        "type": "hello",
        "version": PROTOCOL_VERSION,
        "session_id": session.session_id,
        "audio_params": {
            "format": "mp3",
            "sample_rate": 24000,
        },
    })

    # Send boot animation to display
    boot_cmd = session.display.boot()
    await send_json(session.websocket, boot_cmd)

    # Start display tick loop (idle/sleep transitions)
    asyncio.create_task(display_tick_loop(session))

    logger.info("Session %s ready", session.session_id[:8])


async def handle_set_options(session: ClientSession, msg: dict):
    """Handle client options: internet access, AI model selection."""
    if not session.agent:
        await send_json(session.websocket, {"type": "error", "message": "Send hello first"})
        return

    options = msg.get("options", {})

    # Internet access toggle
    if "internet" in options:
        enabled = bool(options["internet"])
        session.agent.tool_dispatcher.internet_enabled = enabled
        logger.info("Internet %s for %s", "enabled" if enabled else "disabled", session.session_id[:8])

    # AI model selection
    if "model" in options:
        model = options["model"]
        # Only allow known safe models
        allowed_models = {
            "haiku": "claude-haiku-4-5-20251001",
            "sonnet": "claude-sonnet-4-20250514",
        }
        if model in allowed_models:
            from meowbot.config import CLAUDE_MODEL as _  # noqa
            session.agent.client = session.agent.client  # keep client
            # Override model in the agent's call method
            session.agent._model_override = allowed_models[model]
            logger.info("Model set to %s for %s", model, session.session_id[:8])

    await send_json(session.websocket, {
        "type": "options_updated",
        "internet": session.agent.tool_dispatcher.internet_enabled,
        "model": getattr(session.agent, '_model_override', None) or "haiku",
    })


async def handle_get_skills(session: ClientSession):
    """Send list of all available skills with their status."""
    skills = scan_skills()
    enabled = getattr(session, '_enabled_skills', None)
    if enabled is None:
        # Default: all skills enabled
        session._enabled_skills = {s["id"] for s in skills}
        enabled = session._enabled_skills

    result = []
    for s in skills:
        result.append({
            "id": s["id"],
            "name": s.get("name", s["id"]),
            "description": s.get("description", ""),
            "version": s.get("version", "0.0.0"),
            "icon": s.get("icon", "🔧"),
            "category": s.get("category", "other"),
            "tags": s.get("tags", []),
            "enabled": s["id"] in enabled,
        })
    await send_json(session.websocket, {"type": "skills_list", "skills": result})


async def handle_set_skill(session: ClientSession, msg: dict):
    """Enable or disable a specific skill."""
    skill_id = msg.get("skill")
    enabled = msg.get("enabled", True)
    if not hasattr(session, '_enabled_skills'):
        session._enabled_skills = {s["id"] for s in scan_skills()}

    if enabled:
        session._enabled_skills.add(skill_id)
    else:
        session._enabled_skills.discard(skill_id)
        # Don't allow disabling core
        if skill_id == "core":
            session._enabled_skills.add("core")

    logger.info("Skill %s %s for %s", skill_id, "enabled" if enabled else "disabled", session.session_id[:8])
    # Send updated list
    await handle_get_skills(session)


async def handle_run_test(session: ClientSession, msg: dict):
    """Run self-test on skills sequentially, streaming results."""
    skills = scan_skills()
    enabled = getattr(session, '_enabled_skills', {s["id"] for s in skills})
    target = msg.get("skills", "all")

    test_skills = [s for s in skills if s["id"] in enabled and s["id"] != "core"]
    if target != "all":
        target_list = target if isinstance(target, list) else [target]
        test_skills = [s for s in test_skills if s["id"] in target_list]

    await send_json(session.websocket, {
        "type": "test_start",
        "total": len(test_skills),
    })

    for i, skill in enumerate(test_skills):
        sid = skill["id"]
        await send_json(session.websocket, {
            "type": "test_progress",
            "skill": sid,
            "name": skill.get("name", sid),
            "icon": skill.get("icon", "🔧"),
            "index": i,
            "status": "running",
        })

        # Run skill-specific test
        result = await _test_skill(session, sid)

        await send_json(session.websocket, {
            "type": "test_progress",
            "skill": sid,
            "name": skill.get("name", sid),
            "icon": skill.get("icon", "🔧"),
            "index": i,
            "status": result["status"],
            "detail": result.get("detail", ""),
            "duration_ms": result.get("duration_ms", 0),
        })

    await send_json(session.websocket, {"type": "test_end"})


async def _test_skill(session: ClientSession, skill_id: str) -> dict:
    """Test a single skill and return result."""
    import time
    t0 = time.monotonic()

    try:
        if skill_id == "emotion":
            # Test: send a happy phrase, check emotion parsing
            if session.agent:
                response = await asyncio.to_thread(session.agent.think, "Ура! У меня отличные новости!")
                emotion = getattr(session.agent, 'last_emotion', None)
                if emotion:
                    ms = int((time.monotonic() - t0) * 1000)
                    return {"status": "passed", "detail": f"{emotion.primary} {int(emotion.intensity*100)}%", "duration_ms": ms}
            return {"status": "error", "detail": "No agent", "duration_ms": 0}

        elif skill_id == "web_search":
            # Test: check if search module loads
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    results = list(ddgs.text("test query", max_results=1))
                ms = int((time.monotonic() - t0) * 1000)
                return {"status": "passed", "detail": f"{len(results)} result(s)", "duration_ms": ms}
            except Exception as e:
                ms = int((time.monotonic() - t0) * 1000)
                return {"status": "error", "detail": str(e)[:60], "duration_ms": ms}

        elif skill_id == "storyteller":
            # Test: generate a short story
            if session.agent:
                response = await asyncio.to_thread(session.agent.think, "Расскажи очень короткую сказку в одно предложение")
                ms = int((time.monotonic() - t0) * 1000)
                return {"status": "passed", "detail": response[:50] + "...", "duration_ms": ms}
            return {"status": "error", "detail": "No agent", "duration_ms": 0}

        elif skill_id == "reminder":
            # Test: check reminder module is importable
            from meowbot.memory_manager import MemoryManager
            ms = int((time.monotonic() - t0) * 1000)
            return {"status": "passed", "detail": "Module OK", "duration_ms": ms}

        else:
            ms = int((time.monotonic() - t0) * 1000)
            return {"status": "skipped", "detail": "No test defined", "duration_ms": ms}

    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return {"status": "error", "detail": str(e)[:80], "duration_ms": ms}


async def handle_text(session: ClientSession, msg: dict):
    """Handle text message — full conversation flow with display emotions."""
    content = msg.get("content", "").strip()
    if not content:
        await send_json(session.websocket, {"type": "error", "message": "Empty text"})
        return

    if not session.agent:
        await send_json(session.websocket, {"type": "error", "message": "Send hello first"})
        return

    session.aborted = False
    logger.info("Text from %s: %s", session.session_id[:8], content[:50])

    # Backend switch via voice command
    lower = content.lower()
    if "подключи claude" in lower or "switch to claude" in lower:
        session.agent.backend_switcher.force_backend(BackendType.CLAUDE)
        await send_json(session.websocket, {"type": "backend_info", "backend": "claude", "forced": True})
        logger.info("Backend forced to Claude by user")
    elif "подключи ollama" in lower or "switch to ollama" in lower or "локальный режим" in lower:
        session.agent.backend_switcher.auto_backend()
        await send_json(session.websocket, {"type": "backend_info", "backend": "auto"})
        logger.info("Backend set to auto by user")
    elif "подключи gigachat" in lower or "switch to gigachat" in lower:
        session.agent.backend_switcher.force_backend(BackendType.GIGACHAT)
        await send_json(session.websocket, {"type": "backend_info", "backend": "gigachat", "forced": True})
        logger.info("Backend forced to GigaChat by user")

    # Display: show "listening" → "thinking"
    listen_cmd = session.display.setState_direct("listening")
    if listen_cmd:
        await send_json(session.websocket, listen_cmd)

    # Small delay for visual feedback
    await asyncio.sleep(0.3)

    think_cmd = session.display.setState_direct("thinking")
    if think_cmd:
        await send_json(session.websocket, think_cmd)

    # Run LLM pipeline in thread
    response = await asyncio.to_thread(session.agent.think, content)
    logger.info("Response (%s): %s", session.agent._last_backend, response[:50])

    # Send detected emotion to display
    await _send_emotion(session)

    # Send text response + backend info
    await send_json(session.websocket, {"type": "llm", "text": response})
    await send_json(session.websocket, {
        "type": "backend_info",
        "backend": session.agent._last_backend or "unknown",
    })

    # Stream TTS audio with emotion
    await stream_tts(session, response)


async def handle_audio_start(session: ClientSession):
    """Start recording audio from client."""
    session.audio_buffer = bytearray()
    session.recording = True
    session.aborted = False
    logger.debug("Audio recording started for %s", session.session_id[:8])


MAX_AUDIO_BUFFER = 16000 * 2 * 30  # 30 seconds max at 16kHz 16-bit

async def handle_audio_data(session: ClientSession, data: bytes):
    """Buffer incoming PCM audio data."""
    if session.recording:
        if len(session.audio_buffer) + len(data) > MAX_AUDIO_BUFFER:
            logger.warning("Audio buffer overflow from %s, truncating", session.session_id[:8])
            session.recording = False
            return
        session.audio_buffer.extend(data)


async def handle_audio_end(session: ClientSession):
    """Stop recording, run STT → Claude → TTS pipeline."""
    session.recording = False

    if not session.agent:
        await send_json(session.websocket, {"type": "error", "message": "Send hello first"})
        return

    if len(session.audio_buffer) < 1600:  # Less than 0.05s of audio
        await send_json(session.websocket, {"type": "error", "message": "Audio too short"})
        return

    logger.info("Audio received: %d bytes from %s", len(session.audio_buffer), session.session_id[:8])

    # Convert PCM int16 bytes to float32 numpy array
    audio_np = np.frombuffer(bytes(session.audio_buffer), dtype=np.int16).astype(np.float32) / 32768.0
    session.audio_buffer = bytearray()

    # STT in thread
    from meowbot.stt import transcribe
    text = await asyncio.to_thread(transcribe, audio_np)

    if not text:
        await send_json(session.websocket, {"type": "stt", "text": ""})
        await send_json(session.websocket, {"type": "error", "message": "Could not recognize speech"})
        return

    # Send transcription
    await send_json(session.websocket, {"type": "stt", "text": text})
    logger.info("STT: %s", text[:50])

    # Show "listening → thinking" on display
    listening_cmd = session.display.process_touch("double_tap")  # Listening face
    if listening_cmd:
        await send_json(session.websocket, listening_cmd)

    # Send thinking progress to display
    async def send_thinking_progress(step, total, description):
        await send_json(session.websocket, {
            "type": "thinking_progress",
            "step": step,
            "total": total,
            "description": description,
        })
        # Show thinking face
        if step < total:
            thinking_cmd = session.display.setState_direct("thinking")
            if thinking_cmd:
                await send_json(session.websocket, thinking_cmd)

    # Run LLM pipeline (agent.think uses Claude/Ollama via BackendSwitcher)
    response = await asyncio.to_thread(session.agent.think, text)
    logger.info("Response: %s", response[:50])

    # Send detected emotion to display
    await _send_emotion(session)

    # Send response text
    await send_json(session.websocket, {"type": "llm", "text": response})

    # Send backend info
    if hasattr(session.agent, '_last_backend'):
        await send_json(session.websocket, {
            "type": "backend_info",
            "backend": session.agent._last_backend,
        })

    # Stream TTS
    await stream_tts(session, response)


async def _send_emotion(session: ClientSession):
    """Send emotion state to client display."""
    emotion = getattr(session.agent, 'last_emotion', None)
    if emotion:
        # Send raw emotion data
        await send_json(session.websocket, {
            "type": "emotion",
            **emotion.to_dict(),
        })
        # Update display frame based on emotion
        display_cmd = session.display.process_emotion(emotion)
        if display_cmd:
            await send_json(session.websocket, display_cmd)


async def stream_tts(session: ClientSession, text: str):
    """Stream TTS audio as MP3 chunks to client with emotion-adjusted voice."""
    # Get current emotion for voice adjustment
    emotion = "neutral"
    if session.agent and session.agent.last_emotion:
        emotion = session.agent.last_emotion.primary

    await send_json(session.websocket, {"type": "tts_start", "format": "mp3", "emotion": emotion})

    try:
        async for chunk in generate_audio_stream(text, emotion=emotion):
            if session.aborted:
                logger.info("TTS aborted for %s", session.session_id[:8])
                break
            await session.websocket.send(chunk)
    except Exception as e:
        logger.error("TTS streaming error: %s", e)

    await send_json(session.websocket, {"type": "tts_end"})


async def handle_connection(websocket):
    """Main handler for a WebSocket connection."""
    session = ClientSession(websocket=websocket)
    remote = websocket.remote_address
    logger.info("Client connected: %s", remote)

    # P0 Security: Token authentication
    if WS_AUTH_TOKEN:
        try:
            first_msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            try:
                auth = json.loads(first_msg)
            except json.JSONDecodeError:
                auth = {}
            if auth.get("type") != "auth" or auth.get("token") != WS_AUTH_TOKEN:
                await send_json(websocket, {"type": "error", "message": "Authentication failed"})
                await websocket.close(4001, "Unauthorized")
                logger.warning("Auth failed from %s", remote)
                return
            await send_json(websocket, {"type": "auth_ok"})
            logger.info("Auth OK from %s", remote)
        except asyncio.TimeoutError:
            await websocket.close(4002, "Auth timeout")
            logger.warning("Auth timeout from %s", remote)
            return

    try:
        async for message in websocket:
            if isinstance(message, bytes):
                # Binary frame = audio data
                await handle_audio_data(session, message)
                continue

            # Text frame = JSON control message
            try:
                msg = json.loads(message)
            except json.JSONDecodeError:
                await send_json(websocket, {"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type")

            if msg_type == "hello":
                await handle_hello(session, msg)
            elif msg_type == "text":
                await handle_text(session, msg)
            elif msg_type == "audio_start":
                await handle_audio_start(session)
            elif msg_type == "audio_end":
                await handle_audio_end(session)
            elif msg_type == "set_options":
                await handle_set_options(session, msg)
            elif msg_type == "get_skills":
                await handle_get_skills(session)
            elif msg_type == "set_skill":
                await handle_set_skill(session, msg)
            elif msg_type == "run_test":
                await handle_run_test(session, msg)
            elif msg_type == "touch_event":
                gesture = msg.get("gesture", "tap")
                logger.info("Touch %s from %s", gesture, session.session_id[:8])
                # Process touch through display agent
                display_cmd = session.display.process_touch(gesture)
                if display_cmd:
                    await send_json(websocket, display_cmd)
                    # If mic state changed (sleep/wake), handle it
                    if "mic_enabled" in display_cmd:
                        logger.info("Mic %s", "enabled" if display_cmd["mic_enabled"] else "disabled")
            elif msg_type == "ping":
                await send_json(websocket, {"type": "pong", "ts": msg.get("ts")})
            elif msg_type == "abort":
                session.aborted = True
                logger.info("Abort requested by %s", session.session_id[:8])
            else:
                await send_json(websocket, {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except websockets.ConnectionClosed:
        logger.info("Client disconnected: %s", remote)
    except Exception as e:
        logger.error("Connection error: %s", e)
    finally:
        logger.info("Session %s closed", session.session_id[:8])


async def display_tick_loop(session: ClientSession):
    """Background task: periodically check display state (idle/sleep transitions)."""
    while True:
        await asyncio.sleep(2.0)  # Check every 2 seconds
        try:
            if session.websocket.closed:
                break
            cmd = session.display.tick()
            if cmd:
                await send_json(session.websocket, cmd)
        except Exception:
            break


async def serve():
    """Start the WebSocket server."""
    logger.info("Starting AisthOS server on ws://%s:%d", SERVER_HOST, SERVER_PORT)

    async with websockets.serve(
        handle_connection,
        SERVER_HOST,
        SERVER_PORT,
        ping_interval=20,      # Send ping every 20s
        ping_timeout=10,       # Wait 10s for pong before disconnect
        close_timeout=5,       # Wait 5s for clean close
        max_size=2 * 1024 * 1024,  # Max 2MB message size
    ):
        logger.info("Server ready. Waiting for connections...")
        await asyncio.Future()  # Run forever


def main():
    """Entry point for `python -m meowbot.server`."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("Server stopped.")


if __name__ == "__main__":
    main()
