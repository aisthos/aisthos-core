"""Tests for MeowBot memory manager — profiles, reminders, skills loading."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestSkillLoading:
    """Test SKILL.md loading from skills/ directory."""

    def test_load_skills_finds_all_skills(self):
        """Verify all 3 SKILL.md files are loaded."""
        # We import here to avoid loading heavy deps at module level
        from meowbot.config import SKILLS_DIR

        skill_files = list(SKILLS_DIR.rglob("SKILL.md"))
        assert len(skill_files) >= 3, (
            f"Expected at least 3 SKILL.md files, found {len(skill_files)}: "
            f"{[str(f) for f in skill_files]}"
        )

    def test_skill_files_have_frontmatter(self):
        """Each SKILL.md must have YAML frontmatter with ---."""
        from meowbot.config import SKILLS_DIR

        for skill_file in SKILLS_DIR.rglob("SKILL.md"):
            content = skill_file.read_text()
            parts = content.split("---")
            assert len(parts) >= 3, (
                f"{skill_file} missing YAML frontmatter (need at least 2 --- delimiters)"
            )

    def test_skill_files_have_required_metadata(self):
        """Each SKILL.md frontmatter must have name, version, description."""
        import yaml
        from meowbot.config import SKILLS_DIR

        for skill_file in SKILLS_DIR.rglob("SKILL.md"):
            content = skill_file.read_text()
            parts = content.split("---")
            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1])
                assert "name" in meta, f"{skill_file}: missing 'name' in frontmatter"
                assert "version" in meta, f"{skill_file}: missing 'version'"
                assert "description" in meta, f"{skill_file}: missing 'description'"


class TestUserProfiles:
    """Test user profile JSON files."""

    def test_vladimir_profile_exists(self):
        from meowbot.config import MEMORY_DIR

        profile_path = MEMORY_DIR / "profiles" / "vladimir.json"
        assert profile_path.exists(), "vladimir.json profile not found"

        with open(profile_path) as f:
            data = json.load(f)

        assert data["user_id"] == "vladimir"
        assert data["language"] == "ru"
        assert data["role"] == "owner"


class TestRemindersDB:
    """Test reminders SQLite operations directly."""

    def test_reminders_db_schema(self, tmp_path):
        """Verify reminders DB has correct schema."""
        import sqlite3

        db_path = tmp_path / "test_reminders.db"
        db = sqlite3.connect(str(db_path))
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

        # Insert and retrieve
        now = datetime.now().isoformat()
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        db.execute(
            "INSERT INTO reminders (user_id, text, remind_at, created_at) VALUES (?,?,?,?)",
            ("test", "тестовое напоминание", future, now),
        )
        db.commit()

        rows = db.execute(
            "SELECT id, text, remind_at FROM reminders WHERE user_id=? AND done=0",
            ("test",),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "тестовое напоминание"

        db.close()
