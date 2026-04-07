"""Tests for MeowBot tool dispatcher — reminders & storyteller."""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from meowbot.tools import TOOLS, ToolDispatcher


@pytest.fixture
def mock_memory(tmp_path):
    """Create a mock memory with a real SQLite reminders DB."""
    memory = MagicMock()
    memory.user_id = "test_user"

    # Real SQLite for reminders
    db_path = tmp_path / "reminders.db"
    db = sqlite3.connect(str(db_path), check_same_thread=False)
    db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            text TEXT,
            remind_at TEXT,
            done INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    db.commit()
    memory.db = db

    # Mock add_reminder to actually insert into DB
    def _add_reminder(text, remind_at):
        db.execute(
            "INSERT INTO reminders (user_id, text, remind_at, created_at) VALUES (?,?,?,?)",
            ("test_user", text, remind_at, datetime.now().isoformat()),
        )
        db.commit()

    memory.add_reminder = _add_reminder

    # Mock complete_reminder
    def _complete_reminder(reminder_id):
        db.execute("UPDATE reminders SET done=1 WHERE id=?", (reminder_id,))
        db.commit()

    memory.complete_reminder = _complete_reminder

    yield memory
    db.close()


@pytest.fixture
def dispatcher(mock_memory):
    return ToolDispatcher(memory=mock_memory)


class TestToolDefinitions:
    """Verify tool definitions are valid for Claude API."""

    def test_all_tools_have_required_fields(self):
        for tool in TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool['name']} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool['name']} missing 'input_schema'"
            assert tool["input_schema"]["type"] == "object"

    def test_tool_names_are_unique(self):
        names = [t["name"] for t in TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_expected_tools_exist(self):
        names = {t["name"] for t in TOOLS}
        assert "add_reminder" in names
        assert "list_reminders" in names
        assert "complete_reminder" in names
        assert "tell_story" in names


class TestReminderTools:
    """Test reminder tool handlers."""

    def test_add_reminder(self, dispatcher):
        result = dispatcher.dispatch("add_reminder", {
            "text": "покормить кота",
            "minutes_from_now": 30,
        })
        assert result["status"] == "ok"
        assert "покормить кота" in result["message"]
        assert "remind_at" in result

    def test_add_reminder_default_minutes(self, dispatcher):
        result = dispatcher.dispatch("add_reminder", {
            "text": "тест без времени",
        })
        assert result["status"] == "ok"

    def test_list_reminders_empty(self, dispatcher):
        result = dispatcher.dispatch("list_reminders", {})
        assert result["status"] == "ok"
        assert result["reminders"] == []

    def test_list_reminders_with_data(self, dispatcher):
        # Add a reminder first
        dispatcher.dispatch("add_reminder", {
            "text": "позвонить маме",
            "minutes_from_now": 60,
        })
        result = dispatcher.dispatch("list_reminders", {})
        assert result["status"] == "ok"
        assert len(result["reminders"]) == 1
        assert result["reminders"][0]["text"] == "позвонить маме"

    def test_complete_reminder(self, dispatcher):
        # Add then complete
        dispatcher.dispatch("add_reminder", {
            "text": "тест завершения",
            "minutes_from_now": 10,
        })
        reminders = dispatcher.dispatch("list_reminders", {})
        r_id = reminders["reminders"][0]["id"]

        result = dispatcher.dispatch("complete_reminder", {"reminder_id": r_id})
        assert result["status"] == "ok"

        # Should be empty now
        after = dispatcher.dispatch("list_reminders", {})
        assert after["reminders"] == []


class TestStorytellerTools:
    """Test storyteller tool handler."""

    def test_tell_story_default(self, dispatcher):
        result = dispatcher.dispatch("tell_story", {})
        assert result["status"] == "ok"
        assert "instruction" in result
        assert "котики" in result["instruction"]

    def test_tell_story_custom_topic(self, dispatcher):
        result = dispatcher.dispatch("tell_story", {
            "topic": "космос",
            "age": 10,
            "style": "приключение",
        })
        assert result["status"] == "ok"
        assert "космос" in result["instruction"]
        assert "приключение" in result["instruction"]
        assert "10 лет" in result["instruction"]

    def test_tell_story_lullaby(self, dispatcher):
        result = dispatcher.dispatch("tell_story", {
            "style": "колыбельная",
        })
        assert "колыбельная" in result["instruction"]


class TestDispatcherErrors:
    """Test error handling in dispatcher."""

    def test_unknown_tool(self, dispatcher):
        result = dispatcher.dispatch("nonexistent_tool", {})
        assert "error" in result
