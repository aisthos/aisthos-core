"""MeowBot Tools — function definitions for Claude tool use.

Central tool registry. Each skill can define its own tools.py module
with TOOLS list and handler functions. This module collects them all.

Architecture:
  skills/*/SKILL.md  → personality/prompt text (loaded by memory_manager)
  skills/*/tools.py  → tool definitions + handlers (loaded here)
  meowbot/tools.py   → central registry + dispatcher
"""

import logging
import json as json_module
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Import skill tools
from skills.web_search.tools import TOOLS as WEB_SEARCH_TOOLS
from skills.web_search.tools import handle_web_search

# ── Tool Definitions (sent to Claude API) ────────────────────────────

TOOLS: list[dict] = [
    # ── Reminder tools ───────────────────────────────────────────────
    {
        "name": "add_reminder",
        "description": (
            "Поставить напоминание. Используй когда пользователь просит "
            "напомнить о чём-то. Параметр minutes_from_now — через сколько "
            "минут напомнить (по умолчанию 60)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Текст напоминания",
                },
                "minutes_from_now": {
                    "type": "integer",
                    "description": "Через сколько минут напомнить (по умолчанию 60)",
                    "default": 60,
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "list_reminders",
        "description": (
            "Показать все активные напоминания пользователя. "
            "Используй когда спрашивают 'какие у меня напоминания?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "complete_reminder",
        "description": "Отметить напоминание как выполненное по его ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "integer",
                    "description": "ID напоминания для завершения",
                },
            },
            "required": ["reminder_id"],
        },
    },
    # ── Storyteller tools ────────────────────────────────────────────
    {
        "name": "tell_story",
        "description": (
            "Рассказать сказку или историю. Используй когда пользователь "
            "просит рассказать сказку, историю, или что-нибудь интересное. "
            "Можно указать тему и возраст слушателя."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Тема сказки (котики, космос, приключения и т.д.)",
                    "default": "котики",
                },
                "age": {
                    "type": "integer",
                    "description": "Возраст слушателя (для адаптации сложности)",
                    "default": 7,
                },
                "style": {
                    "type": "string",
                    "description": "Стиль: сказка, басня, приключение, колыбельная",
                    "default": "сказка",
                },
            },
        },
    },
    # ── Skill-provided tools ─────────────────────────────────────────
    *WEB_SEARCH_TOOLS,
]


class ToolDispatcher:
    """Dispatches Claude tool calls to the appropriate handler."""

    def __init__(self, memory):
        """
        Args:
            memory: MeowBotMemory instance with reminder methods.
        """
        self.memory = memory
        self.internet_enabled = False  # Disabled by default (parental control)

    def dispatch(self, tool_name: str, tool_input: dict) -> Any:
        """Execute a tool and return the result."""
        handler = getattr(self, f"_handle_{tool_name}", None)
        if handler is None:
            logger.warning("Unknown tool: %s", tool_name)
            return {"error": f"Неизвестный инструмент: {tool_name}"}
        try:
            result = handler(tool_input)
            logger.info("Tool %s executed: %s", tool_name, str(result)[:100])
            return result
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            return {"error": str(e)}

    # ── Reminder handlers ────────────────────────────────────────────

    def _handle_add_reminder(self, inp: dict) -> dict:
        text = inp["text"]
        minutes = inp.get("minutes_from_now", 60)
        remind_at = (datetime.now() + timedelta(minutes=minutes)).isoformat()
        self.memory.add_reminder(text=text, remind_at=remind_at)
        return {
            "status": "ok",
            "message": f"Напоминание '{text}' поставлено через {minutes} мин.",
            "remind_at": remind_at,
        }

    def _handle_list_reminders(self, inp: dict) -> dict:
        # Get all active (not done) reminders, not just pending ones
        rows = self.memory.db.execute(
            "SELECT id, text, remind_at FROM reminders WHERE user_id=? AND done=0",
            (self.memory.user_id,),
        ).fetchall()
        if not rows:
            return {"status": "ok", "reminders": [], "message": "Напоминаний нет."}
        reminders = [
            {"id": r[0], "text": r[1], "remind_at": r[2]} for r in rows
        ]
        return {"status": "ok", "reminders": reminders}

    def _handle_complete_reminder(self, inp: dict) -> dict:
        reminder_id = inp["reminder_id"]
        self.memory.complete_reminder(reminder_id)
        return {"status": "ok", "message": f"Напоминание #{reminder_id} выполнено."}

    # ── Web search handler (delegated to skill) ────────────────────

    def _handle_web_search(self, inp: dict) -> dict:
        """Delegate to web_search skill handler."""
        return handle_web_search(inp, internet_enabled=self.internet_enabled)

    # ── Storyteller handlers ─────────────────────────────────────────

    def _handle_tell_story(self, inp: dict) -> dict:
        """Return story parameters — Claude will generate the story itself."""
        topic = inp.get("topic", "котики")
        age = inp.get("age", 7)
        style = inp.get("style", "сказка")
        return {
            "status": "ok",
            "instruction": (
                f"Расскажи {style} на тему '{topic}' для слушателя {age} лет. "
                f"Сказка должна быть уютной, доброй, 5-8 предложений. "
                f"Рассказывай от первого лица как кот-сказочник. "
                f"Используй звукоподражания: мур, мяу. "
                f"В конце — мораль или тёплое пожелание."
            ),
        }
