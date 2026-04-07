"""Claude text emotion backend — uses [EMOTION:...] tag in Claude responses.

This backend doesn't make separate API calls. Instead, it relies on
the emotion SKILL.md prompt that instructs Claude to prepend an emotion tag
to every response. The tag is parsed by pipeline.parse_emotion_tag().

This is essentially a no-op backend — the real work is done by:
1. SKILL.md → injected into system prompt → Claude generates tag
2. audio_agent.py → calls parse_emotion_tag() on response

This file exists for architecture completeness and future text-only
analysis (e.g., analyzing user input before sending to Claude).
"""

import logging
from typing import Optional

from skills.emotion.backends.base import TextEmotionBackend
from skills.emotion.pipeline import EmotionState

logger = logging.getLogger(__name__)


class ClaudeTextBackend(TextEmotionBackend):
    """Claude-based text emotion — via system prompt tag injection.

    Note: This backend is a pass-through. The actual emotion detection
    happens inside Claude's response (via SKILL.md instructions).
    Use parse_emotion_tag() in audio_agent.py to extract the result.
    """

    async def analyze(
        self,
        text: str,
        context: Optional[list[str]] = None,
    ) -> EmotionState:
        """Quick heuristic text analysis (supplementary to Claude).

        This runs BEFORE Claude responds, providing an initial text signal
        for the fusion pipeline. It's a simple keyword-based fallback.
        """
        text_lower = text.lower()

        # Simple keyword-based emotion hints (Russian)
        sad_words = {"грустно", "расстроен", "печально", "плохо", "ужасно", "тоскливо", "скучаю", "больно", "устал"}
        happy_words = {"ура", "отлично", "супер", "здорово", "радость", "счастлив", "прекрасно", "молодец", "класс"}
        angry_words = {"злой", "бесит", "ненавижу", "раздражает", "достало", "кошмар", "дурак"}
        fear_words = {"страшно", "боюсь", "тревожно", "волнуюсь", "переживаю", "паника"}
        surprise_words = {"ого", "вау", "ничего себе", "неожиданно", "поверить не могу", "серьёзно"}

        words = set(text_lower.split())

        if words & happy_words:
            return EmotionState(primary="happy", intensity=0.6, valence=0.5, arousal=0.5,
                                intent="excited_sharing", confidence=0.3, source="text_hint")
        if words & sad_words:
            return EmotionState(primary="sad", intensity=0.6, valence=-0.5, arousal=0.2,
                                intent="needs_support", confidence=0.3, source="text_hint")
        if words & angry_words:
            return EmotionState(primary="angry", intensity=0.7, valence=-0.6, arousal=0.8,
                                intent="needs_support", confidence=0.3, source="text_hint")
        if words & fear_words:
            return EmotionState(primary="fear", intensity=0.5, valence=-0.4, arousal=0.6,
                                intent="needs_support", confidence=0.3, source="text_hint")
        if words & surprise_words:
            return EmotionState(primary="surprised", intensity=0.5, valence=0.3, arousal=0.7,
                                intent="excited_sharing", confidence=0.3, source="text_hint")

        return EmotionState(primary="neutral", confidence=0.1, source="text_hint")
