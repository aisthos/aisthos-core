"""Tests for MeowBot configuration."""

from pathlib import Path

from meowbot.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    MEMORY_DIR,
    PROJECT_ROOT,
    SAMPLERATE,
    SKILLS_DIR,
)


class TestConfig:
    """Verify configuration values are set correctly."""

    def test_project_root_exists(self):
        assert PROJECT_ROOT.exists()
        assert PROJECT_ROOT.is_dir()

    def test_skills_dir_exists(self):
        assert SKILLS_DIR.exists()
        assert (SKILLS_DIR / "core" / "SKILL.md").exists()

    def test_memory_dir_exists(self):
        assert MEMORY_DIR.exists()

    def test_samplerate_is_16k(self):
        assert SAMPLERATE == 16000

    def test_api_key_is_configured(self):
        """API key should be set in .env (may be empty in CI)."""
        # In production .env must have the key; in CI/tests it may be absent
        assert ANTHROPIC_API_KEY is not None, (
            "ANTHROPIC_API_KEY is None — check .env file exists"
        )

    def test_claude_model_is_set(self):
        assert CLAUDE_MODEL is not None
        assert "claude" in CLAUDE_MODEL.lower()
