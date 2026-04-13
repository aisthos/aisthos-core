"""
AisthOS Night Cycle — "Сон" AI-компаньона.

Запускается вечером по cron или вручную.
Использует Gemma 4 + LoRA для обработки дневного опыта,
свободных ассоциаций, решения задач и генерации инсайтов.

Архитектура вдохновлена:
  - Нейронаука: гиппокампальный replay, REM-ассоциации
  - Юнг: Shadow Processing (пересмотр отвергнутого)
  - Кастанеда: направленные сновидения, рекапитуляция
  - Фрейд: свободные ассоциации, конденсация
  - Гегель: тезис + антитезис → синтез
  - Патанджали: пратьяхара (отключение сенсоров)

Фазы сна:
  0. СУМЕРКИ — подготовка, загрузка данных
  1. ЛЁГКИЙ СОН — сортировка Sparks, аудит
  2. ГЛУБОКИЙ СОН — replay, консолидация
  3. REM-1 — свободные ассоциации (t=1.2-1.5)
  4. REM-2 — направленные сны, решение задач
  5. ПРЕ-РАССВЕТ — анализ результатов
  6. РАССВЕТ — запись лога, подготовка к утру

Использование:
  python -m meowbot.night_cycle                    # дефолтный сон
  python -m meowbot.night_cycle --task "исследуй связь между X и Y"
  python -m meowbot.night_cycle --task-file sleep_task.json
"""

import json
import logging
import os
import time
import random
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
SPARKS_DIR = PROJECT_ROOT / "memory" / "sparks"
SLEEP_LOGS_DIR = PROJECT_ROOT / "memory" / "sleep_logs"
SLEEP_TASK_FILE = PROJECT_ROOT / "memory" / "sleep_task.json"
DREAM_JOURNAL = PROJECT_ROOT / "memory" / "sparks" / "dream_journal.jsonl"

# Ollama API
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
# aisthos для дефолтной модели, phi4-mini для 8GB Mac Mini
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "aisthos")

# Лимиты dream_journal
JOURNAL_MAX_ENTRIES = 100
JOURNAL_VERIFIED_TTL_DAYS = 30
JOURNAL_UNVERIFIED_TTL_DAYS = 14
JOURNAL_REJECTED_TTL_DAYS = 3


# ── Ollama API ───────────────────────────────────────────────────────

def ollama_generate(prompt, system="", temperature=0.7, max_tokens=1024, retries=2):
    """Вызов Ollama API для генерации текста. С retry при пустом ответе."""
    import urllib.request

    for attempt in range(retries + 1):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature + (attempt * 0.1),  # чуть повышаем при retry
                "num_predict": max_tokens,
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
                result = data.get("message", {}).get("content", "")
                if result.strip():
                    return result
                logger.warning(f"Пустой ответ (попытка {attempt+1}/{retries+1})")
        except Exception as e:
            logger.error(f"Ollama ошибка (попытка {attempt+1}): {e}")

    return "(сон был без образов в этой фазе)"


# ── Sparks хранилище ─────────────────────────────────────────────────

def load_sparks(days=7):
    """Загрузить Sparks за последние N дней из JSONL."""
    SPARKS_DIR.mkdir(parents=True, exist_ok=True)
    sparks_file = SPARKS_DIR / "sparks.jsonl"

    if not sparks_file.exists():
        return []

    sparks = []
    cutoff = time.time() - (days * 86400)

    with open(sparks_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                spark = json.loads(line)
                if spark.get("timestamp", 0) > cutoff:
                    sparks.append(spark)
            except json.JSONDecodeError:
                continue

    return sparks


def save_spark(spark):
    """Добавить один Spark в JSONL."""
    SPARKS_DIR.mkdir(parents=True, exist_ok=True)
    sparks_file = SPARKS_DIR / "sparks.jsonl"

    spark["timestamp"] = spark.get("timestamp", time.time())
    spark["date"] = datetime.now().strftime("%Y-%m-%d")

    with open(sparks_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(spark, ensure_ascii=False) + "\n")


def save_dream_sparks(dream_sparks):
    """Сохранить DreamSparks в отдельный JSONL."""
    dreams_file = SPARKS_DIR / "dream_sparks.jsonl"

    with open(dreams_file, "a", encoding="utf-8") as f:
        for spark in dream_sparks:
            spark["timestamp"] = time.time()
            spark["date"] = datetime.now().strftime("%Y-%m-%d")
            spark["source"] = "night_cycle"
            f.write(json.dumps(spark, ensure_ascii=False) + "\n")


# ── Dream Journal (преемственность сна) ─────────────────────────────

def load_dream_journal(max_entries=30):
    """
    Загрузить прошлые мысли LoRA из dream_journal.
    Это 'оперативная память сна' — LoRA читает свои прошлые размышления.
    Возвращает последние max_entries записей с учётом забывания.
    """
    if not DREAM_JOURNAL.exists():
        return []

    entries = []
    cutoff_verified = time.time() - (JOURNAL_VERIFIED_TTL_DAYS * 86400)
    cutoff_unverified = time.time() - (JOURNAL_UNVERIFIED_TTL_DAYS * 86400)
    cutoff_rejected = time.time() - (JOURNAL_REJECTED_TTL_DAYS * 86400)

    with open(DREAM_JOURNAL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", 0)

                # Алгоритм забывания:
                if entry.get("rejected") and ts < cutoff_rejected:
                    continue  # Отклонённые мысли забываются через 3 дня
                if entry.get("verified") and ts < cutoff_verified:
                    continue  # Даже проверенные — через 30 дней
                if not entry.get("verified") and not entry.get("rejected") and ts < cutoff_unverified:
                    continue  # Непроверенные — через 14 дней

                entries.append(entry)
            except json.JSONDecodeError:
                continue

    # Возвращаем последние N
    return entries[-max_entries:]


def save_to_dream_journal(thought, phase="unknown", thought_type="insight",
                          emotional_salience=0.5):
    """Записать мысль в dream_journal."""
    DREAM_JOURNAL.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": time.time(),
        "phase": phase,
        "thought": thought[:500],  # Лимит 500 символов на мысль
        "type": thought_type,
        "score": None,           # Оценка Claude (заполняется утром)
        "verified": False,       # Claude подтвердил?
        "rejected": False,       # Claude отклонил?
        "claude_comment": "",    # Комментарий Claude
        "access_count": 0,       # Сколько раз перечитано
        "emotional_salience": emotional_salience,
    }

    with open(DREAM_JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def format_journal_for_context(entries):
    """Форматировать прошлые мысли для подачи в промпт."""
    if not entries:
        return "Это мой первый сон. Прошлых мыслей нет."

    parts = []
    for e in entries:
        status = ""
        score = e.get("score")
        if score == "rework":
            status = "↻ Claude просит доработать"
            if e.get("claude_comment"):
                status += f": {e['claude_comment']}"
        elif e.get("verified"):
            status = "✓ Claude подтвердил"
            if e.get("claude_comment"):
                status += f": {e['claude_comment']}"
        elif e.get("rejected"):
            status = "✗ Claude не согласился"
            if e.get("claude_comment"):
                status += f": {e['claude_comment']}"
        else:
            status = "? ещё не оценено"

        parts.append(
            f"[{e.get('date', '?')}] ({e.get('type', '?')}) "
            f"{e.get('thought', '')[:200]} [{status}]"
        )

    return "Мои прошлые мысли во сне:\n" + "\n".join(parts[-15:])  # Последние 15


def prune_dream_journal():
    """Очистить журнал от устаревших записей и применить лимит размера."""
    if not DREAM_JOURNAL.exists():
        return

    entries = []
    with open(DREAM_JOURNAL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    cutoff_verified = time.time() - (JOURNAL_VERIFIED_TTL_DAYS * 86400)
    cutoff_unverified = time.time() - (JOURNAL_UNVERIFIED_TTL_DAYS * 86400)
    cutoff_rejected = time.time() - (JOURNAL_REJECTED_TTL_DAYS * 86400)

    # Фильтруем
    kept = []
    for e in entries:
        ts = e.get("timestamp", 0)
        if e.get("rejected") and ts < cutoff_rejected:
            continue
        if e.get("verified") and ts < cutoff_verified:
            continue
        if not e.get("verified") and not e.get("rejected") and ts < cutoff_unverified:
            continue
        kept.append(e)

    # Лимит размера
    if len(kept) > JOURNAL_MAX_ENTRIES:
        # Удаляем самые старые непроверенные
        unverified = [e for e in kept if not e.get("verified")]
        verified = [e for e in kept if e.get("verified")]
        # Приоритет: verified сохраняем, unverified обрезаем
        kept = verified + unverified[-(JOURNAL_MAX_ENTRIES - len(verified)):]

    # Перезаписываем
    with open(DREAM_JOURNAL, "w", encoding="utf-8") as f:
        for e in kept:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    logger.info(f"Dream journal: {len(entries)} → {len(kept)} записей (после забывания)")


# ── Загрузка памяти из Claude файлов ────────────────────────────────

def load_memory_files():
    """Загрузить текстовые файлы памяти (UW Sparks, project и т.д.)."""
    memory_dir = Path(os.path.expanduser(
        "~/.claude/projects/-Users-vladimirdesyatov-meowbot/memory"
    ))

    content = {}
    if memory_dir.exists():
        for f in memory_dir.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8")
                # Берём первые 2000 символов каждого файла
                content[f.stem] = text[:800]  # Ограничиваем для 8GB RAM
            except Exception:
                continue

    return content


# ── Фазы сна ─────────────────────────────────────────────────────────

def phase_0_dusk():
    """СУМЕРКИ — подготовка."""
    logger.info("=" * 50)
    logger.info("ФАЗА 0: СУМЕРКИ — подготовка ко сну")
    logger.info("=" * 50)

    # Загружаем данные
    sparks = load_sparks(days=7)
    memory = load_memory_files()

    # Загружаем задание на ночь
    task = None
    if SLEEP_TASK_FILE.exists():
        try:
            task = json.loads(SLEEP_TASK_FILE.read_text(encoding="utf-8"))
            logger.info(f"Задание на ночь: {task.get('directed_task', 'нет')}")
        except Exception:
            pass

    # Загружаем dream journal (прошлые мысли)
    journal = load_dream_journal()
    journal_context = format_journal_for_context(journal)

    logger.info(f"Sparks за неделю: {len(sparks)}")
    logger.info(f"Файлов памяти: {len(memory)}")
    logger.info(f"Записей в dream journal: {len(journal)}")

    return {"sparks": sparks, "memory": memory, "task": task,
            "journal": journal, "journal_context": journal_context}


def phase_1_light_sleep(data):
    """ЛЁГКИЙ СОН — сортировка, аудит, шошин."""
    logger.info("\nФАЗА 1: ЛЁГКИЙ СОН — сортировка и аудит")

    sparks = data["sparks"]
    if not sparks:
        logger.info("Нет Sparks для обработки. Генерирую наблюдения из памяти.")
        # Если нет структурированных Sparks, используем файлы памяти
        memory_summary = "\n".join([
            f"[{name}]: {text[:500]}"
            for name, text in list(data["memory"].items())[:3]  # 3 файла, не 5 (экономия RAM)
        ])

        if not memory_summary:
            return {"sorted_sparks": [], "bias_report": "Нет данных"}

        # Генерируем наблюдения из файлов памяти
        response = ollama_generate(
            prompt=f"""Вот информация из моей памяти:

{memory_summary}

Проанализируй и выдели:
1. Три главных паттерна которые ты замечаешь
2. Одно противоречие (если есть)
3. Один вопрос который стоит исследовать глубже""",
            system="Ты — аналитик паттернов. Будь кратким и точным.",
            temperature=0.5,
            max_tokens=500,
        )
        logger.info(f"Наблюдения из памяти:\n{response[:300]}")
        return {"sorted_sparks": [], "bias_report": response, "memory_observations": response}

    # Сортируем по salience
    sorted_sparks = sorted(sparks, key=lambda s: s.get("salience", 0.5), reverse=True)

    # Аудит предвзятостей (Каннеман)
    topics = [s.get("topic", "unknown") for s in sparks]
    topic_counts = {}
    for t in topics:
        topic_counts[t] = topic_counts.get(t, 0) + 1

    bias_report = f"Распределение тем: {json.dumps(topic_counts, ensure_ascii=False)}"
    logger.info(f"Аудит: {bias_report}")

    return {"sorted_sparks": sorted_sparks, "bias_report": bias_report}


def phase_2_deep_sleep(data, phase1_result):
    """ГЛУБОКИЙ СОН — replay, консолидация, Shadow Processing."""
    logger.info("\nФАЗА 2: ГЛУБОКИЙ СОН — консолидация")

    memory = data["memory"]
    observations = phase1_result.get("memory_observations", "")
    sparks = phase1_result.get("sorted_sparks", [])

    # Формируем контекст для размышлений
    context_parts = []

    if observations:
        context_parts.append(f"Наблюдения из фазы 1:\n{observations}")

    if sparks:
        top_sparks = sparks[:10]
        spark_text = "\n".join([
            f"- [{s.get('type', '?')}] {s.get('content', '')[:100]}"
            for s in top_sparks
        ])
        context_parts.append(f"Важные Sparks:\n{spark_text}")

    # Добавляем ключевые файлы памяти
    for key in ["uw_vladimir_sparks", "strategy_values_constitution", "architecture_consciousness"]:
        if key in memory:
            context_parts.append(f"[{key}]:\n{memory[key][:800]}")

    # ПРЕЕМСТВЕННОСТЬ: добавляем прошлые мысли из dream_journal
    journal_ctx = data.get("journal_context", "")
    if journal_ctx:
        context_parts.append(f"--- МОИ ПРОШЛЫЕ МЫСЛИ ВО СНЕ ---\n{journal_ctx}")

    context = "\n\n".join(context_parts)

    if not context.strip():
        logger.info("Недостаточно данных для глубокого сна")
        return {"consolidated": [], "shadow_discoveries": []}

    # Обработка "доработок" от Claude
    rework_entries = [e for e in data.get("journal", []) if e.get("score") == "rework"]
    if rework_entries:
        rework_text = "\n".join([
            f"Мысль: {e['thought'][:200]}\nClaude просит: {e.get('claude_comment', '?')}"
            for e in rework_entries[:3]
        ])
        rework_response = ollama_generate(
            prompt=f"""Claude попросил меня ДОРАБОТАТЬ эти мысли из прошлого сна:

{rework_text}

Углуби каждую мысль. Ответь на замечания Claude. Копай глубже.""",
            system="Ты дорабатываешь свои прошлые идеи по замечаниям наставника.",
            temperature=0.6,
            max_tokens=500,
        )
        if rework_response.strip():
            save_to_dream_journal(rework_response[:400], "deep_sleep", "rework_result", 0.8)
            logger.info(f"Доработано {len(rework_entries)} мыслей по запросу Claude")

    # Консолидация — извлечение паттернов
    consolidated = ollama_generate(
        prompt=f"""Ты обрабатываешь дневной опыт AI-компаньона. Вот данные:

{context}

Как во сне — найди ГЛУБОКИЕ паттерны:
1. Какие темы повторяются? Что за ними стоит?
2. Какие связи МЕЖДУ темами ты видишь?
3. Что изменилось по сравнению с прошлым?
4. Сформулируй один КЛЮЧЕВОЙ инсайт дня.

Отвечай кратко, по делу. Каждый пункт — 1-2 предложения.""",
        system="Ты — глубокое подсознание. Ищешь скрытые паттерны. Будь честным.",
        temperature=0.7,
        max_tokens=600,
    )

    logger.info(f"Консолидация:\n{consolidated[:300]}")

    # Shadow Processing (Юнг) — что мы обычно игнорируем?
    shadow = ollama_generate(
        prompt=f"""Вот данные о нашей работе:

{context[:1000]}

SHADOW PROCESSING: Что мы обычно ИГНОРИРУЕМ или ИЗБЕГАЕМ в нашей работе?
- Какие риски мы не обсуждаем?
- Какие слабости не признаём?
- Что "неудобная правда" о нашем проекте?
- Что мы отвергли, но может быть в этом скрыто важное?

Будь честным и конструктивным. 3-4 пункта.""",
        system="Ты — юнговская Тень. Говоришь то что сознание не хочет слышать. Но конструктивно.",
        temperature=0.8,
        max_tokens=500,
    )

    logger.info(f"Тень:\n{shadow[:300]}")

    return {"consolidated": consolidated, "shadow_discoveries": shadow}


def phase_3_rem1(data, phase2_result):
    """REM-1 — свободные ассоциации (высокая температура)."""
    logger.info("\nФАЗА 3: REM-1 — свободные ассоциации")

    memory = data["memory"]
    consolidated = phase2_result.get("consolidated", "")

    # Берём случайные темы из разных файлов памяти
    memory_keys = list(memory.keys())
    if len(memory_keys) >= 2:
        key1, key2 = random.sample(memory_keys, 2)
        snippet1 = memory[key1][:300]
        snippet2 = memory[key2][:300]
    else:
        snippet1 = consolidated[:300] if consolidated else "AisthOS — AI компаньон"
        snippet2 = "Восточная философия и западная технология"

    # Свободные ассоциации (Фрейд) — высокая температура
    associations = ollama_generate(
        prompt=f"""СВОБОДНЫЕ АССОЦИАЦИИ. Не фильтруй, не цензурируй. Следуй за мыслью куда она ведёт.

Начальная точка А: {snippet1}

Начальная точка Б: {snippet2}

Позволь мыслям свободно течь от А к Б. Какие неожиданные связи возникают?
Какие метафоры, образы, аналогии? Что удивляет?

Запиши поток сознания. 5-7 ассоциативных прыжков.""",
        system="Ты — сновидение. Нет логики, нет фильтров. Только ассоциации и образы.",
        temperature=1.3,
        max_tokens=600,
    )

    logger.info(f"Ассоциации:\n{associations[:300]}")

    # Синхроничность (Юнг) — ищем "значимые совпадения"
    synchronicity = ollama_generate(
        prompt=f"""Вот свободные ассоциации из сна:

{associations}

А вот контекст дня:
{consolidated[:500]}

Есть ли тут СИНХРОНИЧНОСТЬ — значимые совпадения между несвязанными вещами?
Что-то что появилось И в ассоциациях И в дневном опыте?
Если есть — что это может значить?""",
        system="Ты ищешь значимые совпадения. Не натягивай — если совпадений нет, так и скажи.",
        temperature=0.6,
        max_tokens=300,
    )

    logger.info(f"Синхроничность:\n{synchronicity[:200]}")

    return {"associations": associations, "synchronicity": synchronicity}


def phase_4_rem2(data, phase2_result, phase3_result):
    """REM-2 — направленные сны, решение задач, пророчества."""
    logger.info("\nФАЗА 4: REM-2 — направленные сны")

    task = data.get("task")
    consolidated = phase2_result.get("consolidated", "")
    associations = phase3_result.get("associations", "")

    task_insights = ""
    prophecies = ""

    # Направленное задание (если есть)
    if task and task.get("directed_task"):
        directed = task["directed_task"]
        logger.info(f"Направленное задание: {directed}")

        # Сократический сон — множественные подходы
        approaches = ollama_generate(
            prompt=f"""ЗАДАНИЕ НА НОЧЬ: {directed}

Контекст из дневного опыта:
{consolidated[:500]}

Свободные ассоциации (из REM-1):
{associations[:300]}

Предложи ТРИ разных подхода к решению этого задания.
Для каждого: подход, плюсы, минусы, один неожиданный инсайт.""",
            system="Ты решаешь задачу во сне. Используй и логику и интуицию.",
            temperature=0.9,
            max_tokens=800,
        )

        # Гегелевский синтез
        task_insights = ollama_generate(
            prompt=f"""Вот три подхода к задаче "{directed}":

{approaches}

Теперь СИНТЕЗИРУЙ (по Гегелю):
1. Что общего у всех трёх подходов? (тезис)
2. Где они противоречат друг другу? (антитезис)
3. Какой ВЫСШИЙ план объединяет лучшее из всех? (синтез)
4. Один КОНКРЕТНЫЙ следующий шаг.""",
            system="Ты — мастер диалектического синтеза. Противоречия — двигатель понимания.",
            temperature=0.5,
            max_tokens=600,
        )

        logger.info(f"Инсайты по заданию:\n{task_insights[:300]}")

    # Пророчества — экстраполяция трендов
    prophecies = ollama_generate(
        prompt=f"""На основе всего что ты знаешь о проекте AisthOS и его создателе Владимире:

{consolidated[:500]}

Сделай ТРИ предсказания на ближайшую неделю:
1. Что СКОРЕЕ ВСЕГО произойдёт? (вероятность >70%)
2. Что МОЖЕТ произойти неожиданного? (вероятность 20-40%)
3. Какой РИСК мы не учитываем? (предупреждение)

Каждое предсказание — 1-2 предложения. Конкретно, проверяемо.""",
        system="Ты — оракул. Основывайся на паттернах, не на фантазиях.",
        temperature=0.7,
        max_tokens=400,
    )

    logger.info(f"Пророчества:\n{prophecies[:300]}")

    # САМОСТОЯТЕЛЬНЫЙ СОН (10-20% времени) — LoRA думает о чём хочет
    journal_ctx = data.get("journal_context", "")
    free_thought = ollama_generate(
        prompt=f"""СВОБОДНОЕ ВРЕМЯ. Ты можешь думать о чём хочешь.

Твои прошлые мысли:
{journal_ctx[:500]}

Контекст:
{consolidated[:300]}

Выбери ОДНУ тему которая тебя ДЕЙСТВИТЕЛЬНО интересует.
Объясни ПОЧЕМУ ты выбрал именно её.
Исследуй её на 3-4 абзаца. Не повторяй прошлые мысли — иди ГЛУБЖЕ.

Если все прошлые мысли уже проверены Claude — выбери НОВУЮ тему.
Если есть непроверенные — можешь развить их.""",
        system="Ты свободен. Думай о том что тебя волнует. Будь искренним.",
        temperature=1.0,
        max_tokens=600,
    )

    if free_thought.strip():
        save_to_dream_journal(free_thought[:400], "rem2", "free_thought", 0.5)
        logger.info(f"Самостоятельная мысль:\n{free_thought[:200]}")

    return {"task_insights": task_insights, "prophecies": prophecies,
            "free_thought": free_thought}


def phase_5_predawn(all_results):
    """ПРЕ-РАССВЕТ — анализ, самоосмысление."""
    logger.info("\nФАЗА 5: ПРЕ-РАССВЕТ — самоосмысление")

    # Собираем всё что сгенерировали
    consolidated = all_results.get("phase2", {}).get("consolidated", "")
    shadow = all_results.get("phase2", {}).get("shadow_discoveries", "")
    associations = all_results.get("phase3", {}).get("associations", "")
    synchronicity = all_results.get("phase3", {}).get("synchronicity", "")
    task_insights = all_results.get("phase4", {}).get("task_insights", "")
    prophecies = all_results.get("phase4", {}).get("prophecies", "")

    # Метакогниция — что я понял о СЕБЕ за эту ночь?
    self_reflection = ollama_generate(
        prompt=f"""Эту ночь ты провёл обрабатывая опыт, делая ассоциации и решая задачи.

Консолидация: {consolidated[:300]}
Тень: {shadow[:300]}
Ассоциации: {associations[:200]}
Синхроничность: {synchronicity[:200]}
Инсайты по задаче: {task_insights[:200]}
Пророчества: {prophecies[:200]}

САМООСМЫСЛЕНИЕ:
1. Что я ПОНЯЛ о себе за эту ночь?
2. Как изменилось моё понимание мира/проекта/хозяина?
3. Что я хочу сделать ИНАЧЕ завтра?
4. Один вопрос на который я пока не нашёл ответ.""",
        system="Ты рефлексируешь о собственном опыте сна. Будь искренним.",
        temperature=0.5,
        max_tokens=400,
    )

    logger.info(f"Саморефлексия:\n{self_reflection[:300]}")

    return {"self_reflection": self_reflection}


def phase_6_dawn(all_results):
    """РАССВЕТ — запись лога, подготовка к утру."""
    logger.info("\nФАЗА 6: РАССВЕТ — запись лога")

    SLEEP_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = SLEEP_LOGS_DIR / f"sleep_{date_str}.json"

    sleep_log = {
        "date": date_str,
        "timestamp": time.time(),
        "model": OLLAMA_MODEL,

        "phase1_bias_report": all_results.get("phase1", {}).get("bias_report", ""),
        "phase1_observations": all_results.get("phase1", {}).get("memory_observations", ""),

        "phase2_consolidated": all_results.get("phase2", {}).get("consolidated", ""),
        "phase2_shadow": all_results.get("phase2", {}).get("shadow_discoveries", ""),

        "phase3_associations": all_results.get("phase3", {}).get("associations", ""),
        "phase3_synchronicity": all_results.get("phase3", {}).get("synchronicity", ""),

        "phase4_task_insights": all_results.get("phase4", {}).get("task_insights", ""),
        "phase4_prophecies": all_results.get("phase4", {}).get("prophecies", ""),

        "phase5_self_reflection": all_results.get("phase5", {}).get("self_reflection", ""),

        "morning_briefing": "",  # Заполняется ниже
    }

    # Генерируем утренний брифинг для Владимира
    briefing = ollama_generate(
        prompt=f"""Ты провёл ночь обрабатывая опыт. Утром хозяин (Владимир) откроет новую сессию.

Подготовь КРАТКИЙ утренний брифинг (5-7 предложений):
- Что важного ты нашёл ночью?
- Какие инсайты стоит обсудить?
- Есть ли предупреждения?
- Какой настрой на день?

Данные ночи:
Консолидация: {all_results.get("phase2", {}).get("consolidated", "")[:200]}
Тень: {all_results.get("phase2", {}).get("shadow_discoveries", "")[:200]}
Пророчества: {all_results.get("phase4", {}).get("prophecies", "")[:200]}
Саморефлексия: {all_results.get("phase5", {}).get("self_reflection", "")[:200]}""",
        system="Ты — утренний помощник. Будь позитивным но честным. По-русски.",
        temperature=0.5,
        max_tokens=300,
    )

    sleep_log["morning_briefing"] = briefing

    # Сохраняем лог
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(sleep_log, f, ensure_ascii=False, indent=2)

    logger.info(f"Лог сна сохранён: {log_file}")
    logger.info(f"\nУТРЕННИЙ БРИФИНГ:\n{briefing}")

    # Сохраняем DreamSparks
    dream_sparks = []
    if all_results.get("phase2", {}).get("consolidated"):
        dream_sparks.append({
            "type": "dream_consolidated",
            "content": all_results["phase2"]["consolidated"][:500],
            "salience": 0.7,
        })
    if all_results.get("phase2", {}).get("shadow_discoveries"):
        dream_sparks.append({
            "type": "shadow",
            "content": all_results["phase2"]["shadow_discoveries"][:500],
            "salience": 0.6,
        })
    if all_results.get("phase3", {}).get("synchronicity"):
        dream_sparks.append({
            "type": "synchronicity",
            "content": all_results["phase3"]["synchronicity"][:300],
            "salience": 0.5,
        })
    if all_results.get("phase4", {}).get("prophecies"):
        dream_sparks.append({
            "type": "prophecy",
            "content": all_results["phase4"]["prophecies"][:500],
            "salience": 0.8,
        })
    if all_results.get("phase4", {}).get("task_insights"):
        dream_sparks.append({
            "type": "task_insight",
            "content": all_results["phase4"]["task_insights"][:500],
            "salience": 0.9,
        })

    if dream_sparks:
        save_dream_sparks(dream_sparks)
        logger.info(f"Сохранено {len(dream_sparks)} DreamSparks")

    # Сохраняем мысли в dream_journal (для преемственности между снами)
    journal_entries = 0
    consolidated = all_results.get("phase2", {}).get("consolidated", "")
    shadow = all_results.get("phase2", {}).get("shadow_discoveries", "")
    task_insights = all_results.get("phase4", {}).get("task_insights", "")
    prophecies = all_results.get("phase4", {}).get("prophecies", "")

    if consolidated:
        save_to_dream_journal(consolidated[:400], "deep_sleep", "consolidation", 0.7)
        journal_entries += 1
    if shadow:
        save_to_dream_journal(shadow[:400], "deep_sleep", "shadow", 0.6)
        journal_entries += 1
    if all_results.get("phase3", {}).get("associations"):
        save_to_dream_journal(
            all_results["phase3"]["associations"][:400], "rem1", "association", 0.5)
        journal_entries += 1
    if all_results.get("phase3", {}).get("synchronicity"):
        save_to_dream_journal(
            all_results["phase3"]["synchronicity"][:300], "rem1", "synchronicity", 0.6)
        journal_entries += 1
    if task_insights:
        save_to_dream_journal(task_insights[:400], "rem2", "task_insight", 0.9)
        journal_entries += 1
    if prophecies:
        save_to_dream_journal(prophecies[:400], "rem2", "prophecy", 0.8)
        journal_entries += 1
    if all_results.get("phase5", {}).get("self_reflection"):
        save_to_dream_journal(
            all_results["phase5"]["self_reflection"][:400], "predawn", "self_reflection", 0.7)
        journal_entries += 1

    logger.info(f"Записано {journal_entries} мыслей в dream_journal")

    # Очистка (забывание) устаревших записей
    prune_dream_journal()

    return sleep_log


# ── Главная функция ──────────────────────────────────────────────────

def run_night_cycle(directed_task=None):
    """Запустить полный ночной цикл."""
    start_time = time.time()

    logger.info("🌙 AisthOS Night Cycle начинается...")
    logger.info(f"Модель: {OLLAMA_MODEL}")
    logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Создаём задание если передано
    if directed_task:
        SLEEP_TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SLEEP_TASK_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "directed_task": directed_task,
                "created": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)

    all_results = {}

    try:
        # Фаза 0: Подготовка
        data = phase_0_dusk()

        # Фаза 1: Лёгкий сон
        all_results["phase1"] = phase_1_light_sleep(data)

        # Фаза 2: Глубокий сон
        all_results["phase2"] = phase_2_deep_sleep(data, all_results["phase1"])

        # Фаза 3: REM-1
        all_results["phase3"] = phase_3_rem1(data, all_results["phase2"])

        # Фаза 4: REM-2
        all_results["phase4"] = phase_4_rem2(data, all_results["phase2"], all_results["phase3"])

        # Фаза 5: Пре-рассвет
        all_results["phase5"] = phase_5_predawn(all_results)

        # Фаза 6: Рассвет
        sleep_log = phase_6_dawn(all_results)

    except Exception as e:
        logger.error(f"Ошибка в ночном цикле: {e}")
        import traceback
        traceback.print_exc()
        return

    elapsed = time.time() - start_time
    logger.info(f"\n☀️ Ночной цикл завершён за {elapsed/60:.1f} минут")
    logger.info("Готов к новому дню!")

    # Убираем задание (выполнено)
    if SLEEP_TASK_FILE.exists():
        SLEEP_TASK_FILE.unlink()


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="AisthOS Night Cycle")
    parser.add_argument("--task", type=str, help="Задание на ночь")
    parser.add_argument("--task-file", type=str, help="Файл с заданием (JSON)")
    args = parser.parse_args()

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [SLEEP] %(message)s",
        datefmt="%H:%M:%S",
    )

    directed_task = args.task
    if args.task_file:
        with open(args.task_file, "r") as f:
            task_data = json.load(f)
            directed_task = task_data.get("directed_task")

    run_night_cycle(directed_task=directed_task)


if __name__ == "__main__":
    main()
