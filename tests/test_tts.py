"""Tests for MeowBot TTS — text cleaning for speech output."""

import pytest

from meowbot.tts import clean_for_speech


class TestCleanForSpeech:
    """Test text cleaning for voice output."""

    def test_strips_emoji(self):
        assert "привет" in clean_for_speech("привет 😀🎉")

    def test_strips_markdown_bold(self):
        result = clean_for_speech("это **важно** слово")
        assert "**" not in result
        assert "важно" in result

    def test_strips_markdown_italic(self):
        result = clean_for_speech("это *курсив* текст")
        assert "*" not in result

    def test_preserves_punctuation(self):
        text = "Привет! Как дела? Хорошо."
        result = clean_for_speech(text)
        assert "!" in result
        assert "?" in result
        assert "." in result

    def test_collapses_whitespace(self):
        result = clean_for_speech("слишком   много    пробелов")
        assert "  " not in result

    def test_empty_string(self):
        assert clean_for_speech("") == ""

    def test_only_emoji_returns_empty(self):
        result = clean_for_speech("😀🎉🐱")
        assert result.strip() == ""

    def test_russian_quotes_preserved(self):
        # «кавычки» should be preserved
        result = clean_for_speech("сказал «привет»")
        assert "привет" in result

    def test_cat_sounds_preserved(self):
        result = clean_for_speech("Мяу! Мррр, как дела?")
        assert "Мяу" in result
        assert "Мррр" in result
