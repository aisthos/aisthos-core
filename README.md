# AisthOS Core

> The brain behind companion robots that grow with you.

AisthOS Core — серверная часть [AisthOS](https://aisthos.dev), открытой платформы для создания эмоциональных AI-компаньонов. Работает на Mac Mini, PC или любом Linux-хосте. Управляет устройствами (ESP32) по WebSocket.

## Что умеет

- **4 LLM-бэкенда** — Ollama (локально) → Claude → GigaChat → Offline с автоматическим переключением
- **Распознавание эмоций** — по голосу (RMS, ZCR, pitch) + по тексту (Claude tag) + fusion
- **Эмоциональный дисплей** — 14 состояний, touch-жесты, sleep/wake, easter eggs
- **5-слойная память** — рабочая, семантическая (ChromaDB), эпизодическая, процедурная, проспективная
- **WebSocket сервер** — протокол совместимый с Xiaozhi ESP32
- **Голос** — Whisper STT + edge-tts с эмоциональной модуляцией
- **Навыки** — напоминания, сказки, веб-поиск, эмоции, погода (в разработке)

## Быстрый старт

```bash
git clone https://github.com/aisthos/aisthos-core.git
cd aisthos-core
pip install -r requirements.txt

# Скопируй .env.example → .env и добавь ключи
cp .env.example .env

# Запуск сервера
python -m meowbot.server
```

Сервер запустится на `ws://127.0.0.1:8765`. Откройте `web/display_simulator.html` в браузере для тестирования.

## Архитектура

```
┌─────────────────────────────────────────-────┐
│              AisthOS Core (Python)           │
│                                              │
│  ┌──────────┐  ┌───────-────┐  ┌──────────┐  │
│  │AudioAgent│  │DisplayAgent│  │  Skills  │  │
│  │ STT → LLM│  │ 14 эмоций  │  │ emotion  │  │
│  │ → TTS    │  │ touch/sleep│  │ reminder │  │
│  └────┬─────┘  └──-───┬─────┘  │ search   │  │
│       │               │        └──────────┘  │
│  ┌────┴───────────────┴──────────────────┐   │
│  │         BackendSwitcher               │   │
│  │  Ollama → Claude → GigaChat → Offline │   │
│  └───────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │           Memory (5 layers)          │    │
│  │  ChromaDB + SQLite + conversation    │    │
│  └──────────────────────────────────────┘    │
└──────────────────┬───────────────────────────┘
                   │ WebSocket
        ┌──────────┴──────────┐
        │   ESP32 устройство  │
        │ (EchoEar/StackChan) │
        │  mic + speaker +    │
        │  display + touch    │
        └─────────────────────┘
```

## Структура проекта

```
meowbot/
├── audio_agent.py      # Оркестратор: STT → LLM → TTS
├── llm_backend.py      # 4 бэкенда с автопереключением
├── display_agent.py    # 14 эмоций, touch, sleep/wake
├── server.py           # WebSocket сервер
├── ws_client.py        # Клиент (для ESP32/тестов)
├── memory_manager.py   # 5-слойная память
├── tools.py            # Диспетчер инструментов
├── tts.py              # Озвучка с эмоциями
├── stt.py              # Распознавание речи
└── config.py           # Конфигурация

skills/
├── emotion/            # Распознавание эмоций (pipeline + backends)
├── greeting/           # Умное приветствие
├── reminder/           # Напоминания
├── storyteller/        # Сказки
├── time_weather/       # Время и погода
└── web_search/         # Веб-поиск (DuckDuckGo)

web/
├── display.js          # Canvas-дисплей (14 эмоций)
├── display_simulator.html  # Симулятор в браузере
└── test_client.html    # Тестовый WebSocket клиент
```

## LLM бэкенды

| Бэкенд | Режим | Модель | Скорость |
|--------|-------|--------|----------|
| Ollama | Локальный | Phi-4-mini (aisthos) | ~28 tok/s |
| Claude | Облако | claude-haiku-4-5 | Быстрый |
| GigaChat | Облако (РФ) | GigaChat | Средний |
| Offline | Без сети | Заготовки ответов | Мгновенный |

Переключение автоматическое: если Ollama недоступен → Claude → GigaChat → Offline.

## Эмоции

14 состояний дисплея: neutral, happy, sad, angry, surprised, fear, love, annoyed, excited, curious, listening, thinking, sleeping, greeting.

Распознавание по двум каналам:
- **Голос**: RMS energy + zero-crossing rate + pitch variance
- **Текст**: Claude добавляет тег `[EMOTION:primary,intensity,valence,arousal,intent]`
- **Fusion**: взвешенное объединение (70% текст + 30% голос)

## Устройства

Поддерживаемые платформы:
- **EchoEar** (ESP32-S3) — основное устройство, круглый дисплей 1.85"
- **StackChan** (ESP32) — планируется
- **Браузер** — `display_simulator.html` для тестирования без железа

## Демо

Попробуйте интерактивную демонстрацию: **[aisthos.dev/demo](https://aisthos.dev/demo/)**

## Лицензия

MIT

## Авторы

Проект создан в сотрудничестве человека и ИИ:
- **Владимир Десятов** — архитектура, продукт, тестирование
- **Claude (Anthropic)** — реализация, документация

> *AisthOS — от греческого aisthesis (восприятие). Grows with you.*
