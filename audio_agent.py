import anthropic
import os
import re
import pyttsx3
import sounddevice as sd
import numpy as np
import tempfile
import scipy.io.wavfile as wav
import mlx_whisper
import torch
from datetime import datetime
from dotenv import load_dotenv

def main():
    # Прогрев Whisper — чтобы первый вопрос не тормозил
    print("⏳ Прогрев модели...")
    import tempfile, scipy.io.wavfile as wav
    silence = np.zeros(SAMPLERATE, dtype=np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav.write(f.name, SAMPLERATE, silence)
        mlx_whisper.transcribe(f.name, path_or_hf_repo=WHISPER_MODEL, language="ru")
    print("✅ Готово!\n")
    
    print("🐱 MeowBot запущен!")
    # ... остальной код

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SAMPLERATE = 16000
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"

# ── Silero VAD ───────────────────────────────────────────────────────
vad_model, vad_utils = torch.hub.load(
    repo_or_dir='snakers4/silero-vad',
    model='silero_vad',
    trust_repo=True
)
(get_speech_timestamps, _, read_audio, *_) = vad_utils

def clean_for_speech(text: str) -> str:
    """Убираем смайлики и markdown для голосового вывода"""
    text = re.sub(r'[^\w\s,.!?;:\-—«»]', '', text, flags=re.UNICODE)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_system_prompt() -> str:
    now = datetime.now()
    date_str = now.strftime("%d %B %Y, %A, %H:%M")
    return f"""Ты MeowBot — милый домашний AI-котик-компаньон.
Сегодня: {date_str}.
Правила:
- Отвечай по-русски, грамотно и литературно
- Коротко: 1-3 предложения
- Тепло, с характером кота
- Иногда используй: мур, мяу, мррр
- Если спрашивают дату/время — отвечай точно
- Отвечай на том языке на котором тебя спрашивают"""

def speak(text: str):
    clean = clean_for_speech(text)
    if not clean.strip():
        return
    engine = pyttsx3.init()
    for v in engine.getProperty('voices'):
        if 'milena' in v.name.lower() or 'milena' in v.id.lower():
            engine.setProperty('voice', v.id)
            break
    engine.setProperty('rate', 155)
    engine.say(clean)
    engine.runAndWait()
    engine.stop()

# История разговора — в начале файла после импортов
conversation_history = []

def think(user_input: str) -> str:
    global conversation_history
    
    # Добавляем сообщение пользователя
    conversation_history.append({
        "role": "user",
        "content": user_input
    })
    
    # Ограничиваем историю последними 10 обменами
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]
    
    message = client.messages.create(
        model=os.getenv("CLAUDE_MODEL"),
        max_tokens=200,
        system=get_system_prompt(),
        messages=conversation_history
    )
    
    response_text = message.content[0].text
    
    # Добавляем ответ кота в историю
    conversation_history.append({
        "role": "assistant",
        "content": response_text
    })
    
    return response_text

def record_with_vad(max_seconds: int = 10, silence_seconds: float = 1.5) -> np.ndarray:
    print("🎤 Слушаю... (говори, остановлюсь сам)")
    chunk_size = 512
    recorded = []
    speech_started = False
    silence_chunks = 0
    silence_limit = int(silence_seconds / (512 / SAMPLERATE))

    with sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype='float32') as stream:
        for _ in range(int(max_seconds * SAMPLERATE / chunk_size)):
            chunk, _ = stream.read(chunk_size)
            chunk_flat = chunk.flatten()
            recorded.append(chunk_flat)

            level = np.abs(chunk_flat).max()
            tensor = torch.from_numpy(chunk_flat)
            speech_prob = vad_model(tensor, SAMPLERATE).item()
            
            # ДИАГНОСТИКА — убери после отладки
            print(f"  уровень={level:.3f} речь={speech_prob:.2f}", end='\r')

            if speech_prob > 0.5:
                speech_started = True
                silence_chunks = 0
            elif speech_started:
                silence_chunks += 1
                if silence_chunks >= silence_limit:
                    break

    print()  # новая строка после диагностики
    return np.concatenate(recorded)

# Стоп-фразы которые Whisper выдаёт на тишину
WHISPER_HALLUCINATIONS = [
    "продолжение следует", "continue", "subtitles by",
    "субтитры", "переведено", "translation", "thank you"
]

def transcribe(audio: np.ndarray) -> str:
    # Проверка уровня звука ДО транскрипции
    if np.abs(audio).max() < 0.02:
        return ""
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav.write(f.name, SAMPLERATE, (audio * 32768).astype(np.int16))
        result = mlx_whisper.transcribe(
            f.name,
            path_or_hf_repo=WHISPER_MODEL,
            language="ru",
            no_speech_threshold=0.6,      # ← фильтр тишины
            condition_on_previous_text=False  # ← не додумывает текст
        )
        text = result["text"].strip()
        
        # Фильтр галлюцинаций
        if any(h in text.lower() for h in WHISPER_HALLUCINATIONS):
            return ""
        
        return text

def main():
    print("🐱 MeowBot запущен!")
    print("Нажми Enter → говори → пауза = конец фразы")
    print("Напиши текст → отправь без голоса")
    print("Напиши 'выход' для остановки\n")

    while True:
        cmd = input("[ Enter = говорить | текст = написать ] ").strip()

        if cmd.lower() in ["выход", "exit", "quit"]:
            speak("Мррр, до встречи!")
            break

        if cmd:
            text = cmd
        else:
            audio = record_with_vad()
            if np.abs(audio).max() < 0.01:
                print("🐱 Тишина... попробуй ещё раз\n")
                continue
            text = transcribe(audio)
            if not text:
                print("🐱 Не расслышал, попробуй ещё раз\n")
                continue

        print(f"🎤 Ты: {text}")
        response = think(text)
        print(f"🐱 MeowBot: {response}\n")
        speak(response)

if __name__ == "__main__":
    main()
