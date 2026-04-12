"""
AisthOS ESP32 WebSocket клиент — MicroPython версия.

Подключается к серверу AisthOS Core по WebSocket,
принимает команды дисплея и отправляет аудио/touch.

Протокол:
  Текст  → JSON (hello, text, touch_event, display, emotion, tts_start/end)
  Бинарь → PCM int16 16kHz (клиент→сервер), MP3 (сервер→клиент)

Оборудование: EchoEar ESP32-S3 (дисплей 360x360, микрофон, динамик, touch)
"""

import json
import time
import gc

# MicroPython-специфичные импорты
try:
    import uasyncio as asyncio
    import uwebsocket
    MICROPYTHON = True
except ImportError:
    # Фолбэк для тестирования на обычном Python
    import asyncio
    MICROPYTHON = False


# ── Конфигурация ─────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "server_host": "192.168.1.100",  # IP Mac Mini в локальной сети
    "server_port": 8765,
    "auth_token": "",                 # WS_AUTH_TOKEN из .env сервера
    "reconnect_delay": 3,            # Секунды между попытками
    "max_reconnect_delay": 30,       # Максимальная задержка
    "ping_interval": 15,             # Секунды между ping
    "device_id": "echoear-001",
}


# ── Состояние устройства ─────────────────────────────────────────────

class DeviceState:
    """Текущее состояние устройства."""

    def __init__(self):
        self.connected = False
        self.session_id = None
        self.current_frame = "boot"    # Текущий кадр дисплея
        self.mic_enabled = True
        self.speaker_enabled = True
        self.recording = False
        self.playing_tts = False
        self.emotion = "neutral"
        self.backend = "unknown"

    def reset(self):
        """Сброс при отключении."""
        self.connected = False
        self.session_id = None
        self.current_frame = "boot"
        self.recording = False
        self.playing_tts = False


# ── Обработчики входящих сообщений ───────────────────────────────────

class MessageHandlers:
    """
    Обработчики сообщений от сервера.
    Каждый метод соответствует типу JSON-сообщения.
    Переопределите нужные методы для интеграции с железом.
    """

    def __init__(self, state: DeviceState):
        self.state = state

    def on_hello(self, msg: dict):
        """Ответ на hello — сервер готов."""
        self.state.session_id = msg.get("session_id", "")
        self.state.connected = True
        print(f"[WS] Сессия: {self.state.session_id[:8]}")

    def on_display(self, msg: dict):
        """Команда смены кадра дисплея."""
        frame = msg.get("frame", "neutral")
        transition = msg.get("transition", "instant")
        duration = msg.get("duration_ms", 300)

        self.state.current_frame = frame

        # Обновляем mic/speaker если указано
        if "mic_enabled" in msg:
            self.state.mic_enabled = msg["mic_enabled"]
        if "servo_enabled" in msg:
            self.state.speaker_enabled = msg["servo_enabled"]

        print(f"[ДИСПЛЕЙ] {frame} ({transition}, {duration}мс)")
        # TODO: вызвать display_driver.show_frame(frame, transition, duration)

    def on_emotion(self, msg: dict):
        """Результат распознавания эмоции."""
        self.state.emotion = msg.get("primary", "neutral")
        intensity = msg.get("intensity", 0.5)
        intent = msg.get("intent", "casual_chat")
        print(f"[ЭМОЦИЯ] {self.state.emotion} ({intensity:.0%}) → {intent}")

    def on_tts_start(self, msg: dict):
        """Начало озвучки — готовим динамик."""
        self.state.playing_tts = True
        emotion = msg.get("emotion", "neutral")
        print(f"[TTS] Начало ({emotion})")
        # TODO: audio_driver.prepare_playback()

    def on_tts_end(self, msg: dict):
        """Конец озвучки."""
        self.state.playing_tts = False
        print("[TTS] Конец")
        # TODO: audio_driver.stop_playback()

    def on_llm(self, msg: dict):
        """Текстовый ответ от LLM."""
        text = msg.get("text", "")
        print(f"[LLM] {text[:80]}")

    def on_stt(self, msg: dict):
        """Результат распознавания речи."""
        text = msg.get("text", "")
        if text:
            print(f"[STT] {text[:80]}")

    def on_backend_info(self, msg: dict):
        """Информация о текущем LLM бэкенде."""
        self.state.backend = msg.get("backend", "unknown")
        print(f"[БЭКЕНД] {self.state.backend}")

    def on_error(self, msg: dict):
        """Ошибка от сервера."""
        print(f"[ОШИБКА] {msg.get('message', 'unknown')}")

    def on_auth_ok(self, msg: dict):
        """Аутентификация пройдена."""
        print("[WS] Авторизация OK")

    def on_pong(self, msg: dict):
        """Ответ на ping."""
        pass  # Тихо

    def on_audio_data(self, data: bytes):
        """Бинарный аудио-чанк (MP3 от TTS)."""
        # TODO: audio_driver.feed_mp3_chunk(data)
        pass


# ── WebSocket клиент ─────────────────────────────────────────────────

class AisthOSClient:
    """
    WebSocket клиент для ESP32.

    Автоматический реконнект с экспоненциальной задержкой.
    Обрабатывает JSON-сообщения и бинарные аудио-данные.
    """

    def __init__(self, config: dict = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.state = DeviceState()
        self.handlers = MessageHandlers(self.state)
        self.ws = None
        self._reconnect_delay = self.config["reconnect_delay"]
        self._running = False

    @property
    def server_url(self) -> str:
        host = self.config["server_host"]
        port = self.config["server_port"]
        return f"ws://{host}:{port}"

    async def connect(self):
        """Подключение к серверу с авторизацией."""
        print(f"[WS] Подключаюсь к {self.server_url}...")

        try:
            if MICROPYTHON:
                self.ws = await uwebsocket.connect(self.server_url)
            else:
                import websockets
                self.ws = await websockets.connect(self.server_url)

            # Авторизация (если токен задан)
            token = self.config["auth_token"]
            if token:
                await self._send_json({"type": "auth", "token": token})
                # Ждём auth_ok
                response = await self._recv()
                if isinstance(response, str):
                    msg = json.loads(response)
                    if msg.get("type") != "auth_ok":
                        print(f"[WS] Авторизация отклонена: {msg}")
                        await self.disconnect()
                        return False
                    self.handlers.on_auth_ok(msg)

            # Отправляем hello
            await self._send_json({
                "type": "hello",
                "device": "echoear",
                "device_id": self.config["device_id"],
                "version": 1,
            })

            self.state.connected = True
            self._reconnect_delay = self.config["reconnect_delay"]
            print("[WS] Подключено!")
            return True

        except Exception as e:
            print(f"[WS] Ошибка подключения: {e}")
            self.state.reset()
            return False

    async def disconnect(self):
        """Отключение от сервера."""
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
        self.state.reset()
        print("[WS] Отключено")

    async def run(self):
        """
        Основной цикл: подключение → приём сообщений → реконнект.
        Запускайте как asyncio.create_task(client.run()).
        """
        self._running = True

        while self._running:
            # Подключаемся
            if not await self.connect():
                delay = self._reconnect_delay
                print(f"[WS] Повтор через {delay}с...")
                await asyncio.sleep(delay)
                # Экспоненциальная задержка
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self.config["max_reconnect_delay"]
                )
                continue

            # Запускаем параллельно: приём сообщений + ping
            try:
                recv_task = asyncio.create_task(self._recv_loop())
                ping_task = asyncio.create_task(self._ping_loop())
                await recv_task
            except Exception as e:
                print(f"[WS] Ошибка: {e}")
            finally:
                ping_task.cancel()
                await self.disconnect()

            if self._running:
                print(f"[WS] Реконнект через {self._reconnect_delay}с...")
                await asyncio.sleep(self._reconnect_delay)

    def stop(self):
        """Остановить клиент."""
        self._running = False

    # ── Отправка ─────────────────────────────────────────────────────

    async def _send_json(self, data: dict):
        """Отправить JSON-сообщение."""
        if self.ws:
            text = json.dumps(data)
            if MICROPYTHON:
                await self.ws.send(text)
            else:
                await self.ws.send(text)

    async def _send_binary(self, data: bytes):
        """Отправить бинарные данные (аудио)."""
        if self.ws:
            await self.ws.send(data)

    async def _recv(self):
        """Принять одно сообщение."""
        if MICROPYTHON:
            return await self.ws.recv()
        else:
            return await self.ws.recv()

    # ── Публичные методы для железа ──────────────────────────────────

    async def send_text(self, text: str):
        """Отправить текст для обработки (как если бы пользователь написал)."""
        await self._send_json({"type": "text", "content": text})

    async def send_touch(self, gesture: str):
        """Отправить touch-событие (tap, pet, long_press, swipe_up и т.д.)."""
        await self._send_json({"type": "touch_event", "gesture": gesture})

    async def start_recording(self):
        """Начать запись аудио."""
        self.state.recording = True
        await self._send_json({"type": "audio_start"})

    async def stop_recording(self):
        """Остановить запись и отправить на распознавание."""
        self.state.recording = False
        await self._send_json({"type": "audio_end"})

    async def send_audio_chunk(self, pcm_data: bytes):
        """Отправить чанк PCM аудио (int16, 16kHz, mono)."""
        if self.state.recording:
            await self._send_binary(pcm_data)

    async def abort(self):
        """Прервать текущую генерацию (TTS/LLM)."""
        await self._send_json({"type": "abort"})

    # ── Приватные циклы ──────────────────────────────────────────────

    async def _recv_loop(self):
        """Цикл приёма сообщений от сервера."""
        while self._running and self.ws:
            try:
                message = await self._recv()
            except Exception as e:
                print(f"[WS] Соединение потеряно: {e}")
                break

            if isinstance(message, bytes):
                # Бинарные данные = MP3 аудио
                self.handlers.on_audio_data(message)
                continue

            # JSON-сообщение
            try:
                msg = json.loads(message)
            except (ValueError, json.JSONDecodeError):
                print(f"[WS] Невалидный JSON: {message[:50]}")
                continue

            msg_type = msg.get("type", "")
            handler = getattr(self.handlers, f"on_{msg_type}", None)
            if handler:
                try:
                    handler(msg)
                except Exception as e:
                    print(f"[WS] Ошибка обработки {msg_type}: {e}")
            else:
                print(f"[WS] Неизвестный тип: {msg_type}")

            # Очистка памяти (важно для ESP32)
            gc.collect()

    async def _ping_loop(self):
        """Отправка ping для поддержания соединения."""
        interval = self.config["ping_interval"]
        while self._running and self.ws:
            await asyncio.sleep(interval)
            try:
                await self._send_json({
                    "type": "ping",
                    "ts": time.time(),
                })
            except Exception:
                break


# ── Точка входа ──────────────────────────────────────────────────────

async def main():
    """Тестовый запуск клиента."""
    config = {
        "server_host": "127.0.0.1",
        "server_port": 8765,
        "auth_token": "",
    }

    client = AisthOSClient(config)

    # Запускаем клиент в фоне
    client_task = asyncio.create_task(client.run())

    # Ждём подключения
    await asyncio.sleep(3)

    if client.state.connected:
        # Тестовые команды
        await client.send_text("Привет! Как дела?")
        await asyncio.sleep(5)

        await client.send_touch("tap")
        await asyncio.sleep(2)

        await client.send_touch("pet")
        await asyncio.sleep(2)

    # Работаем пока не прервут
    try:
        await client_task
    except KeyboardInterrupt:
        client.stop()


if __name__ == "__main__":
    asyncio.run(main())
