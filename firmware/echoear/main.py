"""
AisthOS EchoEar — главный модуль прошивки.

Запуск: автоматически при включении ESP32 (boot.py → main.py).

Цикл работы:
  1. Подключение к WiFi
  2. Подключение к серверу AisthOS Core по WebSocket
  3. Инициализация дисплея, микрофона, динамика
  4. Основной цикл: VAD → запись → отправка → приём → отображение

Конфигурация: config.json на flash или SD-карте.
"""

import json
import time
import gc

try:
    import uasyncio as asyncio
    import network
    MICROPYTHON = True
except ImportError:
    import asyncio
    MICROPYTHON = False

from ws_client import AisthOSClient
from display_driver import DisplayDriver, TouchDetector
from audio_driver import AudioDriver


# ── Конфигурация ─────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "wifi_ssid": "",
    "wifi_password": "",
    "server_host": "192.168.1.100",
    "server_port": 8765,
    "auth_token": "",
    "device_id": "echoear-001",
    "brightness": 80,
    "volume": 70,
}


def load_config() -> dict:
    """Загрузить конфигурацию из config.json."""
    try:
        with open("config.json", "r") as f:
            user_config = json.load(f)
            return {**DEFAULT_CONFIG, **user_config}
    except (OSError, ValueError):
        print("[КОНФИГ] config.json не найден, используем значения по умолчанию")
        return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """Сохранить конфигурацию в config.json."""
    with open("config.json", "w") as f:
        json.dump(config, f)
    print("[КОНФИГ] Сохранено")


# ── WiFi ─────────────────────────────────────────────────────────────

async def connect_wifi(ssid: str, password: str, timeout: int = 15) -> bool:
    """Подключение к WiFi с таймаутом."""
    if not MICROPYTHON:
        print(f"[WIFI] Симуляция подключения к {ssid}")
        return True

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"[WIFI] Уже подключено: {ip}")
        return True

    print(f"[WIFI] Подключаюсь к {ssid}...")
    wlan.connect(ssid, password)

    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > timeout:
            print("[WIFI] Таймаут подключения")
            return False
        await asyncio.sleep(0.5)

    ip = wlan.ifconfig()[0]
    print(f"[WIFI] Подключено: {ip}")
    return True


# ── Основной цикл устройства ─────────────────────────────────────────

class EchoEarDevice:
    """
    Главный класс устройства EchoEar.

    Координирует работу всех компонентов:
    WiFi → WebSocket → Display → Audio → Touch.
    """

    def __init__(self):
        self.config = load_config()
        self.display = DisplayDriver()
        self.audio = AudioDriver()
        self.touch = TouchDetector()
        self.client = None
        self._running = False

    async def start(self):
        """Запуск устройства."""
        print("=" * 40)
        print("  AisthOS EchoEar v0.1")
        print("  Grows with you.")
        print("=" * 40)

        # Инициализация железа
        self.display.init()
        self.display.show_frame("boot")
        self.display.set_brightness(self.config["brightness"])
        self.audio.init()

        # Подключение к WiFi
        wifi_ok = await connect_wifi(
            self.config["wifi_ssid"],
            self.config["wifi_password"],
        )

        if not wifi_ok:
            self.display.show_frame("sad")
            print("[УСТРОЙСТВО] Нет WiFi. Офлайн-режим.")
            # TODO: офлайн-режим (только touch + базовые анимации)
            return

        # WebSocket клиент
        self.client = AisthOSClient({
            "server_host": self.config["server_host"],
            "server_port": self.config["server_port"],
            "auth_token": self.config["auth_token"],
            "device_id": self.config["device_id"],
        })

        # Подключаем обработчики дисплея
        original_on_display = self.client.handlers.on_display

        def on_display_with_driver(msg):
            original_on_display(msg)
            frame = msg.get("frame", "neutral")
            transition = msg.get("transition", "instant")
            self.display.show_frame(frame, transition)

        self.client.handlers.on_display = on_display_with_driver

        # Запуск параллельных задач
        self._running = True
        await asyncio.gather(
            self.client.run(),         # WebSocket + приём сообщений
            self._audio_loop(),        # VAD + отправка аудио
            self._touch_loop(),        # Обработка touch-событий
            self._status_loop(),       # Мониторинг памяти
        )

    async def _audio_loop(self):
        """Цикл записи и отправки аудио."""
        while self._running:
            if not self.client or not self.client.state.connected:
                await asyncio.sleep(1)
                continue

            if not self.client.state.mic_enabled:
                await asyncio.sleep(0.5)
                continue

            # Читаем чанк с микрофона
            chunk = self.audio.read_chunk()
            if chunk is None:
                await asyncio.sleep(0.05)
                continue

            # VAD — определяем начало/конец речи
            event = self.audio.vad.process_chunk(chunk)

            if event == "speech_start":
                await self.client.start_recording()
                self.audio.start_recording()

            if self.client.state.recording:
                await self.client.send_audio_chunk(chunk)

            if event == "speech_end":
                await self.client.stop_recording()
                self.audio.stop_recording()

            await asyncio.sleep(0.01)  # ~100 чанков/сек при 16kHz

    async def _touch_loop(self):
        """Цикл обработки touch-событий."""
        if not MICROPYTHON:
            # В симуляции touch не обрабатываем
            while self._running:
                await asyncio.sleep(1)
            return

        # TODO: чтение I2C от CST816S
        # Пример логики:
        # while self._running:
        #     if touch_irq.value() == 0:  # Прерывание от touch
        #         data = i2c.readfrom(CST816S_ADDR, 6)
        #         event_type = data[1]  # 0=down, 1=up, 2=move
        #         x = ((data[2] & 0x0F) << 8) | data[3]
        #         y = ((data[4] & 0x0F) << 8) | data[5]
        #
        #         if event_type == 0:
        #             self.touch.on_touch_start(x, y)
        #         elif event_type == 1:
        #             gesture = self.touch.on_touch_end(x, y)
        #             if gesture and self.client:
        #                 await self.client.send_touch(gesture)
        #         elif event_type == 2:
        #             self.touch.on_touch_move(x, y)
        #     await asyncio.sleep(0.02)

        while self._running:
            await asyncio.sleep(1)

    async def _status_loop(self):
        """Периодический мониторинг состояния."""
        while self._running:
            gc.collect()
            free_mem = gc.mem_free() if MICROPYTHON else 0
            if MICROPYTHON:
                print(f"[СТАТУС] RAM: {free_mem // 1024}KB свободно | "
                      f"Кадр: {self.display.current_frame} | "
                      f"WS: {'подкл' if self.client and self.client.state.connected else 'откл'}")
            await asyncio.sleep(30)

    def stop(self):
        """Остановка устройства."""
        self._running = False
        if self.client:
            self.client.stop()
        self.display.off()
        print("[УСТРОЙСТВО] Остановлено")


# ── Точка входа ──────────────────────────────────────────────────────

def run():
    """Главная точка входа. Вызывается из boot.py."""
    device = EchoEarDevice()
    try:
        asyncio.run(device.start())
    except KeyboardInterrupt:
        device.stop()
        print("AisthOS EchoEar завершён.")


if __name__ == "__main__":
    run()
