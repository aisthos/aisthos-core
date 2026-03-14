"""MeowBot Memory Manager — 5-layer memory system.

Layers:
  1. Working    — conversation_history (managed by audio_agent)
  2. Semantic   — facts & preferences (ChromaDB collection: facts)
  3. Episodic   — events with timestamps (ChromaDB collection: episodes)
  4. Procedural — skills & learned patterns (SKILL.md files + ChromaDB: procedures)
  5. Prospective — reminders & future intentions (SQLite)
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import anthropic
import chromadb
from sentence_transformers import SentenceTransformer

from meowbot.config import MEMORY_DIR, SKILLS_DIR, ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class MeowBotMemory:
    def __init__(self, user_id: str = "default", anthropic_client=None):
        self.user_id = user_id

        # Ensure directories exist
        for d in ["semantic", "prospective", "profiles"]:
            (MEMORY_DIR / d).mkdir(parents=True, exist_ok=True)

        # Embedder
        logger.info("Loading embedding model...")
        self.embedder = SentenceTransformer(EMBED_MODEL)

        # ChromaDB — persistent client with 3 collections
        self.chroma = chromadb.PersistentClient(path=str(MEMORY_DIR / "semantic"))
        self.facts = self.chroma.get_or_create_collection(
            "facts", metadata={"hnsw:space": "cosine"}
        )
        self.episodes = self.chroma.get_or_create_collection(
            "episodes", metadata={"hnsw:space": "cosine"}
        )
        self.procedures = self.chroma.get_or_create_collection(
            "procedures", metadata={"hnsw:space": "cosine"}
        )

        # Anthropic client (shared with audio_agent if provided)
        self.llm = anthropic_client or anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        # SQLite for reminders
        self._init_reminders_db()

        # User profile
        self._init_profile()

        logger.info("Memory loaded for user: %s", user_id)

    # ── Semantic Memory (Facts) ──────────────────────────────────────

    def remember_facts(self, conversation: list[dict]):
        """Extract facts from conversation and store in ChromaDB."""
        text = "\n".join(f"{m['role']}: {m['content']}" for m in conversation)
        response = self.llm.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    "Извлеки ключевые факты о пользователе из разговора. "
                    "Каждый факт — отдельная строка с '- '. "
                    "Категории: family, preferences, work, health, pets, other. "
                    "Формат: '- [категория] факт'. "
                    "Если фактов нет — ответь 'нет'.\n\n"
                    f"{text}"
                ),
            }],
        )
        facts_text = response.content[0].text
        if "нет" in facts_text.lower() and len(facts_text) < 20:
            return

        facts = [
            line.strip("- ").strip()
            for line in facts_text.split("\n")
            if line.strip().startswith("-")
        ]

        now = datetime.now()
        for i, fact in enumerate(facts):
            if not fact:
                continue
            # Parse optional category tag [category]
            category = "other"
            if fact.startswith("[") and "]" in fact:
                category = fact[1:fact.index("]")].lower()
                fact = fact[fact.index("]") + 1:].strip()

            embedding = self.embedder.encode(fact).tolist()
            doc_id = f"{self.user_id}_fact_{now.timestamp()}_{i}"
            self.facts.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[fact],
                metadatas=[{
                    "user_id": self.user_id,
                    "category": category,
                    "created_at": now.isoformat(),
                    "last_accessed": now.isoformat(),
                }],
            )

        logger.info("Saved %d facts", len(facts))

    def recall_facts(self, query: str, limit: int = 5) -> str:
        """Search semantic memory for relevant facts."""
        if self.facts.count() == 0:
            return ""
        embedding = self.embedder.encode(query).tolist()
        results = self.facts.query(
            query_embeddings=[embedding],
            n_results=min(limit, self.facts.count()),
            where={"user_id": self.user_id},
        )
        if not results["documents"] or not results["documents"][0]:
            return ""
        return "\n".join(f"- {doc}" for doc in results["documents"][0])

    # ── Episodic Memory (Events) ─────────────────────────────────────

    def remember_episode(self, summary: str, topic: str = "", sentiment: str = "neutral"):
        """Store an interaction episode with metadata."""
        now = datetime.now()
        embedding = self.embedder.encode(summary).tolist()
        doc_id = f"{self.user_id}_ep_{now.timestamp()}"
        self.episodes.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[summary],
            metadatas=[{
                "user_id": self.user_id,
                "timestamp": now.isoformat(),
                "topic": topic,
                "sentiment": sentiment,
            }],
        )
        logger.debug("Saved episode: %s", summary[:50])

    def recall_episodes(self, query: str, limit: int = 3) -> str:
        """Search episodic memory for relevant past events."""
        if self.episodes.count() == 0:
            return ""
        embedding = self.embedder.encode(query).tolist()
        results = self.episodes.query(
            query_embeddings=[embedding],
            n_results=min(limit, self.episodes.count()),
            where={"user_id": self.user_id},
        )
        if not results["documents"] or not results["documents"][0]:
            return ""
        lines = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            ts = meta.get("timestamp", "")[:16].replace("T", " ")
            lines.append(f"- [{ts}] {doc}")
        return "\n".join(lines)

    # ── Procedural Memory (Skills & Patterns) ────────────────────────

    def load_skills(self) -> str:
        """Load all SKILL.md personality/behavior definitions."""
        skill_texts = []
        for skill_file in sorted(SKILLS_DIR.rglob("SKILL.md")):
            parts = skill_file.read_text().split("---")
            if len(parts) >= 3:
                skill_texts.append(parts[2].strip())
        result = "\n\n---\n\n".join(skill_texts)
        logger.info("Loaded %d skill(s)", len(skill_texts))
        return result

    def learn_procedure(self, trigger: str, actions: str):
        """Store a learned behavioral pattern."""
        now = datetime.now()
        text = f"Когда: {trigger}\nТогда: {actions}"
        embedding = self.embedder.encode(text).tolist()
        doc_id = f"{self.user_id}_proc_{now.timestamp()}"
        self.procedures.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{
                "user_id": self.user_id,
                "trigger": trigger,
                "created_at": now.isoformat(),
                "success_count": 0,
            }],
        )
        logger.info("Learned procedure: %s", trigger)

    def recall_procedures(self, query: str, limit: int = 3) -> str:
        """Search for relevant learned procedures."""
        if self.procedures.count() == 0:
            return ""
        embedding = self.embedder.encode(query).tolist()
        results = self.procedures.query(
            query_embeddings=[embedding],
            n_results=min(limit, self.procedures.count()),
            where={"user_id": self.user_id},
        )
        if not results["documents"] or not results["documents"][0]:
            return ""
        return "\n".join(f"- {doc}" for doc in results["documents"][0])

    # ── Prospective Memory (Reminders) ───────────────────────────────

    def _init_reminders_db(self):
        db_path = MEMORY_DIR / "prospective" / "reminders.db"
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                text TEXT,
                remind_at TEXT,
                done INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        self.db.commit()

    def add_reminder(self, text: str, remind_at: str):
        """Add a future reminder."""
        self.db.execute(
            "INSERT INTO reminders (user_id, text, remind_at, created_at) VALUES (?,?,?,?)",
            (self.user_id, text, remind_at, datetime.now().isoformat()),
        )
        self.db.commit()
        logger.info("Reminder added: %s at %s", text, remind_at)

    def get_pending_reminders(self) -> list[tuple]:
        """Get reminders that are due now or overdue."""
        now = datetime.now().isoformat()
        return self.db.execute(
            "SELECT id, text, remind_at FROM reminders WHERE user_id=? AND done=0 AND remind_at<=?",
            (self.user_id, now),
        ).fetchall()

    def complete_reminder(self, reminder_id: int):
        """Mark a reminder as done."""
        self.db.execute("UPDATE reminders SET done=1 WHERE id=?", (reminder_id,))
        self.db.commit()

    # ── User Profile ─────────────────────────────────────────────────

    def _init_profile(self):
        self.profile_path = MEMORY_DIR / "profiles" / f"{self.user_id}.json"
        if not self.profile_path.exists():
            self._save_profile({
                "user_id": self.user_id,
                "name": self.user_id,
                "language": "ru",
                "role": "owner",
                "preferences": {},
                "created_at": datetime.now().isoformat(),
            })

    def get_profile(self) -> dict:
        with open(self.profile_path) as f:
            return json.load(f)

    def update_profile(self, updates: dict):
        profile = self.get_profile()
        profile.update(updates)
        self._save_profile(profile)

    def _save_profile(self, data: dict):
        with open(self.profile_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Context Builder ──────────────────────────────────────────────

    def build_context(self, query: str) -> str:
        """Build a unified memory context string for the system prompt."""
        parts = []

        # Profile
        profile = self.get_profile()
        name = profile.get("name", self.user_id)
        if name and name != "default":
            parts.append(f"Собеседник: {name}")

        # Semantic facts
        facts = self.recall_facts(query)
        if facts:
            parts.append(f"Известные факты:\n{facts}")

        # Recent episodes
        episodes = self.recall_episodes(query)
        if episodes:
            parts.append(f"Из прошлых разговоров:\n{episodes}")

        # Pending reminders
        reminders = self.get_pending_reminders()
        if reminders:
            reminder_lines = [f"- {r[1]} (на {r[2]})" for r in reminders]
            parts.append(f"Напоминания:\n" + "\n".join(reminder_lines))

        return "\n\n".join(parts)
