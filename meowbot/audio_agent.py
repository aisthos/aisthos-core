"""MeowBot Audio Agent — voice conversation orchestrator.

Flow: microphone → VAD → Whisper → Claude (with memory + tools) → TTS

Tool use: Claude can invoke tools (reminders, storyteller, etc.)
via the Anthropic tool_use API. The agent handles the tool call loop
automatically.
"""

import json
import logging
import threading
from datetime import datetime

import anthropic
import numpy as np

from meowbot.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from meowbot.llm_backend import BackendSwitcher, BackendType
from meowbot.memory_manager import MeowBotMemory
from meowbot.stt import record_with_vad, transcribe, warmup
from meowbot.tools import TOOLS, ToolDispatcher
from meowbot.tts import speak
from skills.emotion.pipeline import EmotionState, parse_emotion_tag

logger = logging.getLogger(__name__)

# Max tokens for regular replies vs storytelling
MAX_TOKENS_DEFAULT = 200
MAX_TOKENS_STORY = 600


class MeowBotAgent:
    def __init__(self, user_id: str = "default"):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.memory = MeowBotMemory(user_id=user_id, anthropic_client=self.client)
        self.conversation_history: list[dict] = []
        self.skill_text = self.memory.load_skills()
        self.tool_dispatcher = ToolDispatcher(memory=self.memory)
        self.backend_switcher = BackendSwitcher()
        self._model_override = None  # Set by server for model switching
        self._last_backend = None  # Track which backend was used
        self.last_emotion: EmotionState | None = None  # Last detected emotion

    @property
    def active_model(self) -> str:
        """Return the currently active model (override or default)."""
        return self._model_override or CLAUDE_MODEL

    def get_system_prompt(self, memory_context: str = "") -> str:
        """Build system prompt from skills + datetime + memory + options."""
        now = datetime.now()
        date_str = now.strftime("%d %B %Y, %A, %H:%M")

        parts = [self.skill_text]
        parts.append(f"\nСегодня: {date_str}.")

        # Current options status
        internet = getattr(self.tool_dispatcher, 'internet_enabled', False)
        model = self._model_override or CLAUDE_MODEL
        parts.append(f"\nТекущие настройки: интернет={'ВКЛЮЧЁН — можешь использовать web_search' if internet else 'выключен'}, модель={model}.")

        if memory_context:
            parts.append(f"\nИз памяти о собеседнике:\n{memory_context}")

        return "\n".join(parts)

    def think(self, user_input: str) -> str:
        """Process user input through memory + Claude (with tool use) and return response."""
        # 1. Recall relevant memories
        memory_context = self.memory.build_context(user_input)
        if memory_context:
            logger.info("Memory context: %d chars", len(memory_context))

        # 2. Add user message to working memory
        self.conversation_history.append({"role": "user", "content": user_input})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # 3. Call LLM (Ollama/Claude/GigaChat with automatic fallback)
        backend = self.backend_switcher.current_backend
        if backend == BackendType.CLAUDE or (
            self._model_override and "claude" in str(self._model_override).lower()
        ):
            # Claude: use tool calling for full capabilities
            raw_response = self._call_claude_with_tools(memory_context)
            self._last_backend = "claude"
        else:
            # Ollama/GigaChat: simple generate (no tool use)
            system = self.get_system_prompt(memory_context=memory_context)
            llm_response = self.backend_switcher.generate(
                prompt=user_input,
                system=system,
                history=self.conversation_history[:-1],  # Exclude current user message (already in prompt)
            )
            raw_response = llm_response.text
            self._last_backend = llm_response.backend.value

        # 4. Parse emotion tag from response (added by emotion skill)
        emotion, response_text = parse_emotion_tag(raw_response)
        if emotion:
            self.last_emotion = emotion
            logger.info("Emotion: %s (%.1f) intent=%s", emotion.primary, emotion.intensity, emotion.intent)
        else:
            self.last_emotion = EmotionState.default()

        # 5. Add final response to working memory (clean text, no tag)
        self.conversation_history.append({"role": "assistant", "content": response_text})

        # 6. Store in long-term memory in background (non-blocking)
        last_exchange = list(self.conversation_history[-2:])
        emotion_label = self.last_emotion.primary if self.last_emotion else "neutral"
        summary = f"Пользователь: {user_input[:100]} → Кот: {response_text[:100]}"
        topic = user_input[:50]
        threading.Thread(
            target=self._store_memories,
            args=(last_exchange, summary, topic),
            daemon=True,
        ).start()

        return response_text

    def _store_memories(self, exchange: list, summary: str, topic: str):
        """Store facts and episodes in background thread."""
        try:
            self.memory.remember_facts(exchange)
            self.memory.remember_episode(summary=summary, topic=topic)
        except Exception as e:
            logger.error("Background memory store failed: %s", e)

    def _call_claude_with_tools(self, memory_context: str) -> str:
        """Call Claude API with tool use support. Handles tool call loop."""
        max_tokens = MAX_TOKENS_DEFAULT

        # First call — Claude may respond with text or tool_use
        message = self.client.messages.create(
            model=self.active_model,
            max_tokens=max_tokens,
            system=self.get_system_prompt(memory_context=memory_context),
            messages=self.conversation_history,
            tools=TOOLS,
        )

        # Tool call loop (max 3 iterations to prevent infinite loops)
        for _ in range(3):
            if message.stop_reason != "tool_use":
                break

            # Process all tool_use blocks in the response
            tool_results = []
            assistant_content = message.content

            for block in message.content:
                if block.type == "tool_use":
                    logger.info("Tool call: %s(%s)", block.name, json.dumps(block.input, ensure_ascii=False))
                    result = self.tool_dispatcher.dispatch(block.name, block.input)

                    # If storyteller — increase max_tokens for the follow-up
                    if block.name == "tell_story":
                        max_tokens = MAX_TOKENS_STORY

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            # Add assistant message + tool results to conversation
            self.conversation_history.append({"role": "assistant", "content": assistant_content})
            self.conversation_history.append({"role": "user", "content": tool_results})

            # Follow-up call with tool results
            message = self.client.messages.create(
                model=self.active_model,
                max_tokens=max_tokens,
                system=self.get_system_prompt(memory_context=memory_context),
                messages=self.conversation_history,
                tools=TOOLS,
            )

        # Extract final text response
        text_parts = [block.text for block in message.content if block.type == "text"]
        return " ".join(text_parts) if text_parts else "Мяу?"

    def _check_pending_reminders(self):
        """Check for due reminders and return announcement if any."""
        reminders = self.memory.get_pending_reminders()
        if not reminders:
            return None
        announcements = []
        for r_id, text, remind_at in reminders:
            announcements.append(f"Мяу! Напоминаю: {text}")
            self.memory.complete_reminder(r_id)
        return " ".join(announcements)

    def run(self):
        """Main conversation loop."""
        warmup()
        logger.info("MeowBot started!")
        speak("Мяу! Я готов!")

        print("[ Enter = говорить | текст = написать | 'выход' = стоп ]\n")

        while True:
            # Check for pending reminders before each interaction
            reminder_text = self._check_pending_reminders()
            if reminder_text:
                print(f"MeowBot: {reminder_text}\n")
                speak(reminder_text)

            try:
                cmd = input("> ").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if cmd.lower() in ("выход", "exit", "quit"):
                speak("Мррр, до встречи!")
                break

            if cmd:
                text = cmd
            else:
                audio = record_with_vad()
                if np.abs(audio).max() < 0.01:
                    print("Тишина... попробуй ещё раз\n")
                    continue
                text = transcribe(audio)
                if not text:
                    print("Не расслышал, попробуй ещё раз\n")
                    continue

            logger.info("User: %s", text)
            response = self.think(text)
            logger.info("MeowBot: %s", response)
            print(f"MeowBot: {response}\n")
            speak(response)


def main():
    agent = MeowBotAgent(user_id="vladimir")
    agent.run()
