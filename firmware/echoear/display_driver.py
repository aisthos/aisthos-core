"""
AisthOS ESP32 Display Driver — управление круглым дисплеем EchoEar.

Дисплей: 1.85" IPS, 360×360 px, touch (CST816S).
Контроллер: ST7789 (SPI).

Задачи:
  - Загрузка и отображение кадров эмоций (BMP/PNG → framebuffer)
  - Плавные переходы (crossfade, fade_in, instant)
  - Обработка touch-жестов (tap, pet, long_press, swipe)

Примечание: на ESP32 нет PIL/Pillow — используем raw framebuffer.
Кадры хранятся на SD-карте или во flash как raw RGB565.
"""

import time

# MicroPython-специфичные импорты
try:
    from machine import Pin, SPI, I2C
    import framebuf
    MICROPYTHON = True
except ImportError:
    MICROPYTHON = False
    print("[ДИСПЛЕЙ] Режим симуляции (не ESP32)")


# ── Конфигурация пинов EchoEar ───────────────────────────────────────

# SPI дисплей (ST7789)
DISPLAY_SPI = 1
DISPLAY_SCK = 12
DISPLAY_MOSI = 11
DISPLAY_CS = 10
DISPLAY_DC = 9
DISPLAY_RST = 8
DISPLAY_BL = 46     # Подсветка

# Touch (CST816S, I2C)
TOUCH_SDA = 4
TOUCH_SCL = 5
TOUCH_INT = 6
TOUCH_RST = 7

# Размеры дисплея
WIDTH = 360
HEIGHT = 360


# ── Список кадров эмоций ─────────────────────────────────────────────

EMOTION_FRAMES = {
    "neutral":   "/frames/neutral.raw",
    "happy":     "/frames/happy.raw",
    "sad":       "/frames/sad.raw",
    "angry":     "/frames/angry.raw",  # используем annoyed
    "surprised": "/frames/surprised.raw",
    "fear":      "/frames/sad.raw",     # фолбэк на sad
    "love":      "/frames/love.raw",
    "annoyed":   "/frames/annoyed.raw",
    "excited":   "/frames/excited.raw",
    "curious":   "/frames/curious.raw",
    "listening": "/frames/listening.raw",
    "thinking":  "/frames/thinking.raw",
    "sleeping":  "/frames/sleeping.raw",
    "greeting":  "/frames/greeting.raw",
    "boot":      "/frames/boot.raw",
    "nyan":      "/frames/nyan.raw",
}


# ── Touch жесты ──────────────────────────────────────────────────────

class TouchDetector:
    """
    Определяет жест по последовательности touch-событий.

    Жесты:
      - tap: короткое нажатие < 300мс
      - long_press: удержание > 1000мс
      - pet: плавное горизонтальное движение
      - swipe_up / swipe_down: вертикальный свайп
      - double_tap: два тапа за 500мс
    """

    def __init__(self):
        self.touch_start = None
        self.touch_start_pos = None
        self.last_tap_time = 0
        self.tap_count = 0

    def on_touch_start(self, x: int, y: int):
        """Палец коснулся экрана."""
        self.touch_start = time.ticks_ms()
        self.touch_start_pos = (x, y)

    def on_touch_end(self, x: int, y: int):
        """Палец отпустил. Возвращает имя жеста или None."""
        if self.touch_start is None:
            return None

        duration = time.ticks_diff(time.ticks_ms(), self.touch_start)
        dx = x - self.touch_start_pos[0]
        dy = y - self.touch_start_pos[1]
        distance = (dx * dx + dy * dy) ** 0.5

        self.touch_start = None

        # Длинное нажатие
        if duration > 1000 and distance < 30:
            self.tap_count = 0
            return "long_press"

        # Свайп (расстояние > 50px)
        if distance > 50:
            self.tap_count = 0
            if abs(dy) > abs(dx):
                return "swipe_up" if dy < 0 else "swipe_down"
            else:
                # Горизонтальное движение = "поглаживание"
                return "pet"

        # Тап (короткий, мало движения)
        if duration < 300 and distance < 30:
            now = time.ticks_ms()
            if time.ticks_diff(now, self.last_tap_time) < 500:
                self.tap_count += 1
                self.last_tap_time = now
                if self.tap_count >= 2:
                    self.tap_count = 0
                    return "double_tap"
                return None  # Ждём возможного double_tap
            else:
                self.tap_count = 1
                self.last_tap_time = now
                return "tap"

        return None

    def on_touch_move(self, x: int, y: int):
        """Палец движется по экрану (для будущего circle-жеста)."""
        pass


# ── Display Driver ───────────────────────────────────────────────────

class DisplayDriver:
    """
    Управление дисплеем EchoEar.

    Методы:
      init()          — инициализация SPI + дисплей
      show_frame(name) — показать кадр эмоции
      set_brightness(0-100) — подсветка
      off()           — выключить дисплей
    """

    def __init__(self):
        self.current_frame = None
        self.brightness = 100
        self._initialized = False

    def init(self):
        """Инициализация дисплея и touch."""
        if not MICROPYTHON:
            print("[ДИСПЛЕЙ] Симуляция — init()")
            self._initialized = True
            return

        # SPI для дисплея
        self.spi = SPI(
            DISPLAY_SPI,
            baudrate=80_000_000,
            polarity=0,
            phase=0,
            sck=Pin(DISPLAY_SCK),
            mosi=Pin(DISPLAY_MOSI),
        )
        self.cs = Pin(DISPLAY_CS, Pin.OUT, value=1)
        self.dc = Pin(DISPLAY_DC, Pin.OUT)
        self.rst = Pin(DISPLAY_RST, Pin.OUT)
        self.bl = Pin(DISPLAY_BL, Pin.OUT)

        # Сброс дисплея
        self.rst.value(0)
        time.sleep_ms(50)
        self.rst.value(1)
        time.sleep_ms(100)

        # ST7789 инициализация (базовая последовательность)
        self._init_st7789()

        # Подсветка включена
        self.bl.value(1)
        self._initialized = True
        print("[ДИСПЛЕЙ] Инициализирован")

    def _init_st7789(self):
        """Последовательность инициализации ST7789 360x360."""
        # TODO: полная последовательность команд ST7789
        # Зависит от конкретной ревизии EchoEar
        # Будет доработана после получения устройства
        pass

    def show_frame(self, frame_name: str, transition: str = "instant"):
        """
        Показать кадр эмоции на дисплее.

        Args:
            frame_name: имя из EMOTION_FRAMES (neutral, happy, ...)
            transition: instant, crossfade, fade_in, slow_fade
        """
        if frame_name == self.current_frame:
            return

        path = EMOTION_FRAMES.get(frame_name)
        if not path:
            print(f"[ДИСПЛЕЙ] Неизвестный кадр: {frame_name}")
            return

        if not MICROPYTHON:
            print(f"[ДИСПЛЕЙ] {self.current_frame} → {frame_name} ({transition})")
            self.current_frame = frame_name
            return

        # Загрузка raw RGB565 файла и вывод на дисплей
        try:
            with open(path, "rb") as f:
                # TODO: буферизированная загрузка по строкам
                # (360*360*2 = 259200 байт — не влезет целиком в RAM)
                # Решение: читаем и выводим построчно
                for y in range(HEIGHT):
                    line = f.read(WIDTH * 2)  # 2 байта на пиксель (RGB565)
                    self._write_line(y, line)

            self.current_frame = frame_name
        except OSError:
            print(f"[ДИСПЛЕЙ] Файл не найден: {path}")

    def _write_line(self, y: int, data: bytes):
        """Записать одну строку пикселей на дисплей."""
        # TODO: реализация через SPI
        # self._set_window(0, y, WIDTH-1, y)
        # self.dc.value(1)
        # self.cs.value(0)
        # self.spi.write(data)
        # self.cs.value(1)
        pass

    def set_brightness(self, percent: int):
        """Установить яркость подсветки (0-100)."""
        self.brightness = max(0, min(100, percent))
        if MICROPYTHON:
            # TODO: PWM на пине подсветки
            if self.brightness == 0:
                self.bl.value(0)
            else:
                self.bl.value(1)
        print(f"[ДИСПЛЕЙ] Яркость: {self.brightness}%")

    def off(self):
        """Выключить дисплей (sleep mode)."""
        self.set_brightness(0)
        if MICROPYTHON:
            # ST7789 sleep command
            pass
        print("[ДИСПЛЕЙ] Выключен")


# ── Конвертация изображений ──────────────────────────────────────────

def convert_png_to_raw(input_path: str, output_path: str, width: int = 360, height: int = 360):
    """
    Конвертирует PNG в raw RGB565 для ESP32.
    Запускать на компьютере (не на ESP32!), результат копировать на SD.

    RGB565: 5 бит красный, 6 бит зелёный, 5 бит синий = 2 байта/пиксель.
    """
    from PIL import Image
    import struct

    img = Image.open(input_path).convert("RGB").resize((width, height))

    with open(output_path, "wb") as f:
        for y in range(height):
            for x in range(width):
                r, g, b = img.getpixel((x, y))
                # RGB888 → RGB565
                rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                f.write(struct.pack(">H", rgb565))  # Big-endian

    print(f"Конвертировано: {input_path} → {output_path} ({width}x{height}, RGB565)")
