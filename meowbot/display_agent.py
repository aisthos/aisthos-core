"""AisthOS Display Agent — maps emotions to visual frames on device screen.

Converts EmotionState from the emotion pipeline into display commands
for the ESP32 device (EchoEar, StackChan, etc.).

Architecture:
  EmotionState → DisplayAgent → WebSocket → ESP32 → Screen

Frames are pre-generated images (14 emotions) stored on the device.
This module decides WHICH frame to show and WHEN to transition.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DisplayFrame(str, Enum):
    """Available emotion frames on the device display."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    LISTENING = "listening"
    THINKING = "thinking"
    SLEEPING = "sleeping"
    SURPRISED = "surprised"
    SAD = "sad"
    LOVE = "love"
    ANNOYED = "annoyed"
    EXCITED = "excited"
    CURIOUS = "curious"
    GREETING = "greeting"
    BOOT = "boot"
    NYAN = "nyan"


# Mapping: emotion primary → display frame
EMOTION_TO_FRAME = {
    "happy": DisplayFrame.HAPPY,
    "sad": DisplayFrame.SAD,
    "angry": DisplayFrame.ANNOYED,
    "neutral": DisplayFrame.NEUTRAL,
    "surprised": DisplayFrame.SURPRISED,
    "fear": DisplayFrame.SAD,  # Fear shows as concern/sad
}

# Mapping: intent → display frame override
INTENT_TO_FRAME = {
    "needs_support": DisplayFrame.SAD,
    "wants_advice": DisplayFrame.CURIOUS,
    "casual_chat": None,  # Use emotion-based frame
    "excited_sharing": DisplayFrame.EXCITED,
    "focused_work": DisplayFrame.THINKING,
}

# Touch gesture → display response
TOUCH_RESPONSES = {
    "tap": DisplayFrame.SURPRISED,
    "double_tap": DisplayFrame.LISTENING,
    "long_press": DisplayFrame.SLEEPING,
    "swipe_up": DisplayFrame.CURIOUS,
    "swipe_down": DisplayFrame.NEUTRAL,  # Mute mode
    "pet": DisplayFrame.LOVE,
    "poke_repeated": DisplayFrame.ANNOYED,
    "circle": DisplayFrame.HAPPY,
}


@dataclass
class DisplayState:
    """Current state of the device display."""
    current_frame: DisplayFrame = DisplayFrame.NEUTRAL
    is_sleeping: bool = False
    is_muted: bool = False
    last_interaction: float = field(default_factory=time.time)
    pet_count: int = 0  # Consecutive pets for love escalation
    poke_count: int = 0  # Consecutive pokes for annoyance
    boot_complete: bool = False

    # Idle timeout: switch to neutral after N seconds of no emotion change
    IDLE_TIMEOUT = 10.0
    # Sleep timeout: auto-sleep after N seconds of no interaction
    AUTO_SLEEP_TIMEOUT = 300.0  # 5 minutes


class DisplayAgent:
    """Manages emotion display on the companion device.

    Usage:
        agent = DisplayAgent()

        # From emotion pipeline
        frame_cmd = agent.process_emotion(emotion_state)

        # From touch events
        frame_cmd = agent.process_touch("pet")

        # Periodic check (idle/sleep transitions)
        frame_cmd = agent.tick()
    """

    def __init__(self):
        self.state = DisplayState()
        logger.info("DisplayAgent initialized")

    def setState_direct(self, frame_name: str) -> Optional[dict]:
        """Directly set a display frame by name. Used by server for conversation flow.

        Args:
            frame_name: One of DisplayFrame values (neutral, listening, thinking, etc.)

        Returns:
            Display command dict or None if no change
        """
        try:
            frame = DisplayFrame(frame_name)
        except ValueError:
            return None

        if frame == self.state.current_frame:
            return None

        if self.state.is_sleeping:
            return None

        self.state.current_frame = frame
        self.state.last_interaction = time.time()
        return self._make_command(frame, transition="crossfade", duration_ms=200)

    def boot(self) -> dict:
        """Generate boot animation command."""
        self.state.boot_complete = True
        self.state.current_frame = DisplayFrame.BOOT
        logger.info("Display: BOOT sequence")
        return self._make_command(DisplayFrame.BOOT, transition="fade_in", duration_ms=2000)

    def process_emotion(self, emotion) -> Optional[dict]:
        """Convert EmotionState to display frame command.

        Args:
            emotion: EmotionState from the emotion pipeline

        Returns:
            Display command dict or None if no change needed
        """
        if self.state.is_sleeping:
            return None  # Don't change display while sleeping

        self.state.last_interaction = time.time()

        # Check intent-based override first
        intent = getattr(emotion, 'intent', 'casual_chat')
        intent_frame = INTENT_TO_FRAME.get(intent)

        if intent_frame:
            new_frame = intent_frame
        else:
            # Map primary emotion to frame
            primary = getattr(emotion, 'primary', 'neutral')
            new_frame = EMOTION_TO_FRAME.get(primary, DisplayFrame.NEUTRAL)

        # High intensity surprise → extra sparkle
        intensity = getattr(emotion, 'intensity', 0.5)
        if primary == "happy" and intensity > 0.8:
            new_frame = DisplayFrame.EXCITED

        # Only send if changed
        if new_frame == self.state.current_frame:
            return None

        self.state.current_frame = new_frame
        self.state.pet_count = 0  # Reset touch counters on emotion change
        self.state.poke_count = 0

        transition = "crossfade" if new_frame != DisplayFrame.SURPRISED else "instant"
        logger.info("Display: %s → %s", self.state.current_frame, new_frame)
        return self._make_command(new_frame, transition=transition)

    def process_touch(self, gesture: str) -> Optional[dict]:
        """Handle touch gesture and return display command.

        Args:
            gesture: One of tap, double_tap, long_press, pet, poke_repeated,
                     swipe_up, swipe_down, swipe_left, swipe_right, circle
        """
        self.state.last_interaction = time.time()

        # Wake from sleep on any touch
        if self.state.is_sleeping and gesture != "long_press":
            return self._wake_up()

        # Sleep on long press
        if gesture == "long_press":
            if self.state.is_sleeping:
                return self._wake_up()
            else:
                return self._go_to_sleep()

        # Mute toggle on swipe down
        if gesture == "swipe_down":
            self.state.is_muted = not self.state.is_muted
            logger.info("Display: Mute %s", "ON" if self.state.is_muted else "OFF")
            return self._make_command(
                self.state.current_frame,
                overlay="mute" if self.state.is_muted else None
            )

        # Pet counter → escalate to love
        if gesture == "pet":
            self.state.pet_count += 1
            self.state.poke_count = 0
            if self.state.pet_count >= 5:
                new_frame = DisplayFrame.LOVE
            elif self.state.pet_count >= 2:
                new_frame = DisplayFrame.HAPPY
            else:
                new_frame = DisplayFrame.HAPPY
            self.state.current_frame = new_frame
            logger.info("Display: Pet x%d → %s", self.state.pet_count, new_frame)
            return self._make_command(new_frame, transition="crossfade")

        # Poke counter → escalate to annoyed
        if gesture == "poke_repeated" or (gesture == "tap" and self.state.poke_count > 0):
            self.state.poke_count += 1
            self.state.pet_count = 0
            if self.state.poke_count >= 4:
                new_frame = DisplayFrame.ANNOYED
            else:
                new_frame = DisplayFrame.SURPRISED
            self.state.current_frame = new_frame
            logger.info("Display: Poke x%d → %s", self.state.poke_count, new_frame)
            return self._make_command(new_frame, transition="instant")

        # Standard gesture mapping
        new_frame = TOUCH_RESPONSES.get(gesture, DisplayFrame.NEUTRAL)

        # Tap starts poke counter
        if gesture == "tap":
            self.state.poke_count = 1
            self.state.pet_count = 0

        if new_frame != self.state.current_frame:
            self.state.current_frame = new_frame
            logger.info("Display: Touch '%s' → %s", gesture, new_frame)
            return self._make_command(new_frame, transition="crossfade")

        return None

    def show_backend_status(self, backend: str) -> dict:
        """Show which LLM backend is active as overlay on display.

        Args:
            backend: One of 'ollama', 'claude', 'gigachat', 'offline'
        """
        icons = {
            "ollama": "🏠",     # Local
            "claude": "☁️",     # Cloud
            "gigachat": "🇷🇺",  # Russian cloud
            "offline": "📴",    # Offline
        }
        icon = icons.get(backend, "❓")
        logger.info("Display: backend overlay → %s %s", icon, backend)
        return self._make_command(
            self.state.current_frame,
            overlay=f"backend_{backend}",
            extras={"backend_icon": icon, "backend_name": backend},
        )

    def process_nyan_code(self) -> dict:
        """Easter egg: Nyan Cat mode activated by secret knock."""
        self.state.current_frame = DisplayFrame.NYAN
        logger.info("Display: 🌈 NYAN MODE ACTIVATED")
        return self._make_command(DisplayFrame.NYAN, transition="rainbow", duration_ms=5000)

    def tick(self) -> Optional[dict]:
        """Periodic check for idle/sleep transitions. Call every ~1 second.

        Returns:
            Display command if state changed, None otherwise
        """
        if self.state.is_sleeping:
            return None

        now = time.time()
        elapsed = now - self.state.last_interaction

        # Auto-return to neutral after idle timeout
        if elapsed > self.state.IDLE_TIMEOUT and self.state.current_frame not in (
            DisplayFrame.NEUTRAL, DisplayFrame.SLEEPING
        ):
            self.state.current_frame = DisplayFrame.NEUTRAL
            self.state.pet_count = 0
            self.state.poke_count = 0
            logger.info("Display: Idle → NEUTRAL")
            return self._make_command(DisplayFrame.NEUTRAL, transition="slow_fade")

        # Auto-sleep after long inactivity
        if elapsed > self.state.AUTO_SLEEP_TIMEOUT:
            return self._go_to_sleep()

        return None

    def _go_to_sleep(self) -> dict:
        """Transition to sleep mode."""
        self.state.is_sleeping = True
        self.state.current_frame = DisplayFrame.SLEEPING
        self.state.pet_count = 0
        self.state.poke_count = 0
        logger.info("Display: 😴 Going to sleep")
        return self._make_command(
            DisplayFrame.SLEEPING,
            transition="slow_fade",
            duration_ms=1500,
            extras={"mic_enabled": False, "servo_enabled": False}
        )

    def _wake_up(self) -> dict:
        """Wake from sleep mode."""
        self.state.is_sleeping = False
        self.state.current_frame = DisplayFrame.GREETING
        self.state.last_interaction = time.time()
        logger.info("Display: ☀️ Waking up!")
        return self._make_command(
            DisplayFrame.GREETING,
            transition="fade_in",
            duration_ms=800,
            extras={"mic_enabled": True, "servo_enabled": True}
        )

    def _make_command(
        self,
        frame: DisplayFrame,
        transition: str = "instant",
        duration_ms: int = 300,
        overlay: Optional[str] = None,
        extras: Optional[dict] = None,
    ) -> dict:
        """Build display command dict for WebSocket transmission."""
        cmd = {
            "type": "display",
            "frame": frame.value,
            "transition": transition,
            "duration_ms": duration_ms,
        }
        if overlay:
            cmd["overlay"] = overlay
        if extras:
            cmd.update(extras)
        return cmd
