"""MeowBot Audio Agent — voice conversation orchestrator.

Flow: microphone → VAD → Whisper → Claude (with memory) → TTS
"""

import logging
from datetime import datetime

import anthropic
import numpy as np

from meowbot.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from meowbot.memory_manager import MeowBotMemory
from meowbot.stt import record_with_vad, transcribe, warmup
from meowbot.tts import speak

logger = logging.getLogger(__name__)


class MeowBotAgent:
    def __init__(self, user_id: str = "default"):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.memory = MeowBotMemory(user_id=user_id, anthropic_client=self.client)
        self.conversation_history: list[dict] = []
        self.skill_text = self.memory.load_skills()

    def get_system_prompt(self, memory_context: str = "") -> str:
        """Build system prompt from skills + datetime + memory."""
        now = datetime.now()
        date_str = now.strftime("%d %B %Y, %A, %H:%M")

        parts = [self.skill_text]
        parts.append(f"\nСегодня: {date_str}.")

        if memory_context:
            parts.append(f"\nИз памяти о собеседнике:\n{memory_context}")

        return "\n".join(parts)

    def think(self, user_input: str) -> str:
        """Process user input through memory + Claude and return response."""
        # 1. Recall relevant memories
        memory_context = self.memory.build_context(user_input)
        if memory_context:
            logger.info("Memory context: %d chars", len(memory_context))

        # 2. Add user message to working memory
        self.conversation_history.append({"role": "user", "content": user_input})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # 3. Call Claude with enriched system prompt
        message = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            system=self.get_system_prompt(memory_context=memory_context),
            messages=self.conversation_history,
        )
        response_text = message.content[0].text

        # 4. Add response to working memory
        self.conversation_history.append({"role": "assistant", "content": response_text})

        # 5. Store in long-term memory (semantic + episodic)
        last_exchange = self.conversation_history[-2:]
        self.memory.remember_facts(last_exchange)
        self.memory.remember_episode(
            summary=f"Пользователь: {user_input[:100]} → Кот: {response_text[:100]}",
            topic=user_input[:50],
        )

        return response_text

    def run(self):
        """Main conversation loop."""
        warmup()
        logger.info("MeowBot started!")
        speak("Мяу! Я готов!")

        print("[ Enter = говорить | текст = написать | 'выход' = стоп ]\n")

        while True:
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
