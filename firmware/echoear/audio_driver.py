"""
AisthOS ESP32 Audio Driver — микрофон и динамик EchoEar.

Микрофон: I2S вход (INMP441 или аналог)
Динамик: I2S выход (MAX98357A или аналог)

Задачи:
  - Запись PCM int16 16kHz mono
  - Воспроизведение MP3 (через мини-декодер)
  - VAD (Voice Activity Detection) — определение начала/конца речи
"""

import time

try:
    from machine import Pin, I2S
    import struct
    MICROPYTHON = True
except ImportError:
    MICROPYTHON = False
    print("[АУДИО] Режим симуляции (не ESP32)")


# ── Конфигурация пинов ───────────────────────────────────────────────

# Микрофон (I2S IN)
MIC_SCK = 14     # Serial Clock
MIC_WS = 15      # Word Select
MIC_SD = 16      # Serial Data

# Динамик (I2S OUT)
SPK_SCK = 17
SPK_WS = 18
SPK_SD = 21

# Параметры аудио
SAMPLE_RATE = 16000
CHANNELS = 1
BITS = 16
CHUNK_SIZE = 1024  # байт на чанк (512 сэмплов)


# ── VAD (Voice Activity Detection) ───────────────────────────────────

class SimpleVAD:
    """
    Простой детектор голосовой активности на основе RMS энергии.

    Логика:
      - Если RMS > порога → речь
      - Если тишина > timeout → конец речи
      - Адаптивный порог (обновляется по уровню шума)
    """

    def __init__(self, threshold: float = 500.0, silence_timeout: float = 1.5):
        self.threshold = threshold
        self.silence_timeout = silence_timeout  # секунды тишины = конец речи
        self.is_speaking = False
        self.silence_start = None
        self.noise_level = 200.0  # Базовый уровень шума (адаптивный)

    def process_chunk(self, pcm_data: bytes) -> str:
        """
        Обрабатывает чанк PCM и возвращает событие.

        Возвращает:
          "speech_start" — начало речи
          "speech_end"   — конец речи
          "speaking"     — речь продолжается
          "silence"      — тишина
        """
        # RMS энергии чанка
        rms = self._compute_rms(pcm_data)

        # Адаптивный порог (медленно следует за шумом)
        if not self.is_speaking:
            self.noise_level = self.noise_level * 0.95 + rms * 0.05
            effective_threshold = max(self.threshold, self.noise_level * 3)
        else:
            effective_threshold = self.threshold

        if rms > effective_threshold:
            self.silence_start = None
            if not self.is_speaking:
                self.is_speaking = True
                return "speech_start"
            return "speaking"
        else:
            if self.is_speaking:
                if self.silence_start is None:
                    self.silence_start = time.time()
                elif time.time() - self.silence_start > self.silence_timeout:
                    self.is_speaking = False
                    self.silence_start = None
                    return "speech_end"
                return "speaking"  # Ещё ждём
            return "silence"

    @staticmethod
    def _compute_rms(pcm_data: bytes) -> float:
        """Вычислить RMS энергию из PCM int16."""
        if len(pcm_data) < 2:
            return 0.0

        n_samples = len(pcm_data) // 2
        sum_sq = 0

        for i in range(n_samples):
            # Читаем int16 little-endian
            lo = pcm_data[i * 2]
            hi = pcm_data[i * 2 + 1]
            sample = lo | (hi << 8)
            if sample > 32767:
                sample -= 65536
            sum_sq += sample * sample

        return (sum_sq / n_samples) ** 0.5


# ── Audio Driver ─────────────────────────────────────────────────────

class AudioDriver:
    """
    Управление микрофоном и динамиком.

    Методы:
      init()              — инициализация I2S
      start_recording()   — начать запись
      read_chunk()        — прочитать чанк PCM
      stop_recording()    — остановить запись
      play_mp3_chunk()    — воспроизвести MP3 чанк
      stop_playback()     — остановить воспроизведение
    """

    def __init__(self):
        self.mic = None
        self.spk = None
        self.vad = SimpleVAD()
        self._recording = False
        self._playing = False

    def init(self):
        """Инициализация I2S микрофона и динамика."""
        if not MICROPYTHON:
            print("[АУДИО] Симуляция — init()")
            return

        # Микрофон (I2S вход)
        self.mic = I2S(
            0,
            sck=Pin(MIC_SCK),
            ws=Pin(MIC_WS),
            sd=Pin(MIC_SD),
            mode=I2S.RX,
            bits=BITS,
            format=I2S.MONO,
            rate=SAMPLE_RATE,
            ibuf=4096,
        )

        # Динамик (I2S выход)
        self.spk = I2S(
            1,
            sck=Pin(SPK_SCK),
            ws=Pin(SPK_WS),
            sd=Pin(SPK_SD),
            mode=I2S.TX,
            bits=BITS,
            format=I2S.MONO,
            rate=SAMPLE_RATE,
            ibuf=4096,
        )

        print("[АУДИО] Инициализирован")

    def start_recording(self):
        """Начать запись с микрофона."""
        self._recording = True
        print("[АУДИО] Запись начата")

    def read_chunk(self):
        """Прочитать чанк PCM данных с микрофона."""
        if not self._recording:
            return None

        if not MICROPYTHON:
            # Симуляция: возвращаем тишину
            return bytes(CHUNK_SIZE)

        buf = bytearray(CHUNK_SIZE)
        num_read = self.mic.readinto(buf)
        if num_read > 0:
            return bytes(buf[:num_read])
        return None

    def stop_recording(self):
        """Остановить запись."""
        self._recording = False
        print("[АУДИО] Запись остановлена")

    def play_pcm_chunk(self, data: bytes):
        """Воспроизвести чанк PCM через динамик."""
        if not MICROPYTHON:
            return

        if self.spk:
            self.spk.write(data)

    def stop_playback(self):
        """Остановить воспроизведение."""
        self._playing = False
        print("[АУДИО] Воспроизведение остановлено")

    def prepare_playback(self):
        """Подготовить динамик к воспроизведению."""
        self._playing = True
        print("[АУДИО] Готов к воспроизведению")
