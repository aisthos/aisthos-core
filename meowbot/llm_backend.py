"""AisthOS LLM Backend Switcher — automatic fallback between Ollama and Claude API.

Architecture:
  1. Ollama (local, free, private) — default
  2. Claude API (cloud, paid, powerful) — for complex tasks or when Ollama unavailable
  3. Offline (no LLM) — only cached skills work

User can force Claude API via voice command or touch gesture.
Backend automatically falls back: Ollama → Claude → Offline.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "aisthos")


class BackendType(str, Enum):
    OLLAMA = "ollama"
    CLAUDE = "claude"
    GIGACHAT = "gigachat"
    DEEPSEEK = "deepseek"
    OFFLINE = "offline"


@dataclass
class LLMResponse:
    """Response from any LLM backend."""
    text: str
    backend: BackendType
    model: str
    tokens_used: int = 0
    thinking_steps: list = None  # For progress display

    def __post_init__(self):
        if self.thinking_steps is None:
            self.thinking_steps = []


class OllamaBackend:
    """Local Ollama backend — free, private, fast for simple tasks."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model

    def is_available(self) -> bool:
        """Check if Ollama is running and model is loaded."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                available = any(self.model in m for m in models)
                if available:
                    logger.debug("Ollama available: %s", self.model)
                else:
                    logger.debug("Ollama running but model '%s' not found. Available: %s", self.model, models)
                return available
        except Exception as e:
            logger.debug("Ollama not available: %s", e)
            return False

    def generate(self, prompt: str, system: str = "", history: list = None) -> LLMResponse:
        """Generate response from Ollama."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_ctx": 4096,
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                text = data.get("message", {}).get("content", "")
                tokens = data.get("eval_count", 0)
                logger.info("Ollama response: %d tokens, model=%s", tokens, self.model)
                return LLMResponse(
                    text=text,
                    backend=BackendType.OLLAMA,
                    model=self.model,
                    tokens_used=tokens,
                )
        except Exception as e:
            logger.error("Ollama generate error: %s", e)
            raise


GIGACHAT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1"
GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"


class GigaChatBackend:
    """Sber GigaChat backend — for Russian market (152-FZ compliant).

    Requires GIGACHAT_CREDENTIALS env var (client_id:client_secret base64).
    Get credentials at developers.sber.ru/portal/products/gigachat-api
    """

    def __init__(self):
        self.credentials = os.getenv("GIGACHAT_CREDENTIALS", "")
        self.model = os.getenv("GIGACHAT_MODEL", "GigaChat")
        self._access_token: Optional[str] = None

    def is_available(self) -> bool:
        """Check if GigaChat credentials are configured."""
        return bool(self.credentials)

    def _get_token(self) -> str:
        """Get OAuth access token from Sber."""
        if self._access_token:
            return self._access_token

        import ssl
        import base64

        payload = "scope=GIGACHAT_API_PERS".encode("utf-8")
        req = urllib.request.Request(
            GIGACHAT_AUTH_URL,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Authorization": f"Basic {self.credentials}",
                "RqUID": str(os.urandom(16).hex()),
            },
            method="POST",
        )

        # GigaChat uses self-signed cert — need to disable verification
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read())
                self._access_token = data["access_token"]
                return self._access_token
        except Exception as e:
            logger.error("GigaChat auth error: %s", e)
            raise

    def generate(self, prompt: str, system: str = "", history: list = None) -> LLMResponse:
        """Generate response from GigaChat API."""
        import ssl

        token = self._get_token()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{GIGACHAT_API_URL}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                data = json.loads(resp.read())
                text = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                logger.info("GigaChat response: %d tokens, model=%s", tokens, self.model)
                return LLMResponse(
                    text=text,
                    backend=BackendType.GIGACHAT,
                    model=self.model,
                    tokens_used=tokens,
                )
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self._access_token = None  # Token expired, retry
                logger.warning("GigaChat token expired, will retry")
            logger.error("GigaChat API error: %s", e)
            raise


DEEPSEEK_API_URL = "https://api.deepseek.com/v1"


class DeepSeekBackend:
    """DeepSeek API — дешёвый облачный бэкенд для Basic-тира подписки.

    OpenAI-совместимый формат. $0.28/$0.42 за 1M токенов — в 11 раз дешевле Claude.
    Без географических ограничений (доступен из России).

    Получить ключ: platform.deepseek.com
    """

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    def is_available(self) -> bool:
        """Проверяет наличие API ключа."""
        return bool(self.api_key)

    def generate(self, prompt: str, system: str = "", history: list = None) -> LLMResponse:
        """Генерация ответа через DeepSeek API (OpenAI-совместимый формат)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{DEEPSEEK_API_URL}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                text = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                logger.info("DeepSeek: %d токенов, модель=%s", tokens, self.model)
                return LLMResponse(
                    text=text,
                    backend=BackendType.DEEPSEEK,
                    model=self.model,
                    tokens_used=tokens,
                )
        except Exception as e:
            logger.error("DeepSeek API ошибка: %s", e)
            raise


class BackendSwitcher:
    """Manages LLM backend selection with automatic fallback.

    Priority: Ollama (local) → Claude → GigaChat → Offline
    For Russian market: GigaChat can be forced as default.

    Usage:
        switcher = BackendSwitcher()
        response = switcher.generate(prompt, system_prompt)
        print(response.text, response.backend)
    """

    def __init__(self):
        self.ollama = OllamaBackend()
        self.gigachat = GigaChatBackend()
        self.deepseek = DeepSeekBackend()
        self._forced_backend: Optional[BackendType] = None
        self._ollama_available: Optional[bool] = None
        logger.info("BackendSwitcher: GigaChat=%s, DeepSeek=%s",
                     "да" if self.gigachat.is_available() else "нет",
                     "да" if self.deepseek.is_available() else "нет")

    @property
    def current_backend(self) -> BackendType:
        """Return the currently active backend."""
        if self._forced_backend:
            return self._forced_backend
        if self._ollama_available is None:
            self._ollama_available = self.ollama.is_available()
        if self._ollama_available:
            return BackendType.OLLAMA
        # Check if Claude API key exists
        from meowbot.config import ANTHROPIC_API_KEY
        if ANTHROPIC_API_KEY:
            return BackendType.CLAUDE
        # Check GigaChat
        if self.gigachat.is_available():
            return BackendType.GIGACHAT
        # Check DeepSeek
        if self.deepseek.is_available():
            return BackendType.DEEPSEEK
        return BackendType.OFFLINE

    def force_backend(self, backend: BackendType):
        """Force a specific backend (user request)."""
        self._forced_backend = backend
        logger.info("Backend forced to: %s", backend)

    def auto_backend(self):
        """Return to automatic backend selection."""
        self._forced_backend = None
        self._ollama_available = None  # Re-check on next call
        logger.info("Backend set to auto")

    def generate(self, prompt: str, system: str = "", history: list = None,
                 on_thinking: callable = None) -> LLMResponse:
        """Generate response using best available backend.

        Args:
            prompt: User message
            system: System prompt
            history: Conversation history
            on_thinking: Callback for progress updates (for display)
                         Called with (step_num, total_steps, description)

        Returns:
            LLMResponse with text and backend info
        """
        backend = self.current_backend

        # Notify display about backend being used
        if on_thinking:
            on_thinking(0, 1, f"Using {backend.value}...")

        if backend == BackendType.OLLAMA:
            try:
                if on_thinking:
                    on_thinking(1, 2, "Ollama thinking...")
                response = self.ollama.generate(prompt, system, history)
                if on_thinking:
                    on_thinking(2, 2, "Done!")
                return response
            except Exception as e:
                logger.warning("Ollama failed, falling back to Claude: %s", e)
                self._ollama_available = False
                backend = BackendType.CLAUDE

        if backend == BackendType.CLAUDE:
            if on_thinking:
                on_thinking(1, 3, "Connecting to Claude API...")
            try:
                response = self._generate_claude(prompt, system, history, on_thinking)
                return response
            except Exception as e:
                logger.warning("Claude failed, trying GigaChat: %s", e)
                backend = BackendType.GIGACHAT

        if backend == BackendType.GIGACHAT:
            if on_thinking:
                on_thinking(1, 3, "Connecting to GigaChat...")
            try:
                response = self._generate_gigachat(prompt, system, history, on_thinking)
                return response
            except Exception as e:
                logger.warning("GigaChat failed, trying DeepSeek: %s", e)
                backend = BackendType.DEEPSEEK

        if backend == BackendType.DEEPSEEK:
            if on_thinking:
                on_thinking(1, 3, "Connecting to DeepSeek...")
            try:
                response = self._generate_deepseek(prompt, system, history, on_thinking)
                return response
            except Exception as e:
                logger.warning("DeepSeek failed: %s", e)

        # Offline fallback
        return LLMResponse(
            text="Я сейчас в автономном режиме. Могу отвечать на базовые команды и использовать сохранённые навыки.",
            backend=BackendType.OFFLINE,
            model="none",
        )

    def _generate_claude(self, prompt: str, system: str = "", history: list = None,
                         on_thinking: callable = None) -> LLMResponse:
        """Generate using Claude API."""
        import anthropic
        from meowbot.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

        if not ANTHROPIC_API_KEY:
            return LLMResponse(
                text="Claude API key not configured. Please set ANTHROPIC_API_KEY in .env",
                backend=BackendType.OFFLINE,
                model="none",
            )

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        if on_thinking:
            on_thinking(2, 3, "Claude is thinking...")

        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                system=system,
                messages=messages,
            )

            text = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens

            if on_thinking:
                on_thinking(3, 3, "Done!")

            logger.info("Claude response: %d tokens, model=%s", tokens, CLAUDE_MODEL)
            return LLMResponse(
                text=text,
                backend=BackendType.CLAUDE,
                model=CLAUDE_MODEL,
                tokens_used=tokens,
            )
        except Exception as e:
            logger.error("Claude API error: %s", e)
            return LLMResponse(
                text=f"Error connecting to Claude: {str(e)[:100]}",
                backend=BackendType.OFFLINE,
                model="none",
            )

    def _generate_gigachat(self, prompt: str, system: str = "", history: list = None,
                           on_thinking: callable = None) -> LLMResponse:
        """Generate using GigaChat API (Sber, Russia)."""
        if not self.gigachat.is_available():
            raise RuntimeError("GigaChat not configured")

        if on_thinking:
            on_thinking(2, 3, "GigaChat думает...")

        response = self.gigachat.generate(prompt, system, history)

        if on_thinking:
            on_thinking(3, 3, "Готово!")

        return response

    def _generate_deepseek(self, prompt: str, system: str = "", history: list = None,
                           on_thinking: callable = None) -> LLMResponse:
        """Генерация через DeepSeek API (дешёвый облачный бэкенд)."""
        if not self.deepseek.is_available():
            raise RuntimeError("DeepSeek не настроен")

        if on_thinking:
            on_thinking(2, 3, "DeepSeek думает...")

        response = self.deepseek.generate(prompt, system, history)

        if on_thinking:
            on_thinking(3, 3, "Готово!")

        return response

    def get_status(self) -> dict:
        """Return current backend status for display."""
        return {
            "active_backend": self.current_backend.value,
            "forced": self._forced_backend is not None,
            "ollama_available": self.ollama.is_available(),
            "ollama_model": self.ollama.model,
            "gigachat_available": self.gigachat.is_available(),
            "deepseek_available": self.deepseek.is_available(),
            "backends": ["ollama", "claude", "gigachat", "deepseek", "offline"],
        }
