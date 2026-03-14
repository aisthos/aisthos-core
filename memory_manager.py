import os, json, sqlite3, anthropic
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer

load_dotenv()
BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

class MeowBotMemory:
    def __init__(self, user_id="default"):
        self.user_id = user_id
        for d in ["semantic","prospective","profiles"]:
            (MEMORY_DIR / d).mkdir(parents=True, exist_ok=True)
        self.embedder = SentenceTransformer(EMBED_MODEL)
        self.chroma = chromadb.PersistentClient(path=str(MEMORY_DIR / "semantic"))
        self.collection = self.chroma.get_or_create_collection("meowbot_memory", metadata={"hnsw:space": "cosine"})
        self.llm = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._init_prospective_db()
        self._init_profile()
        print(f"🧠 Память загружена для: {user_id}")

    def remember(self, conversation):
        text = "\n".join(f"{m['role']}: {m['content']}" for m in conversation)
        response = self.llm.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role":"user","content":f'Извлеки ключевые факты. Каждый факт — строка с "- ". Если нет — ответь "нет".\n\n{text}'}]
        )
        facts_text = response.content[0].text
        if "нет" in facts_text.lower() and len(facts_text) < 20:
            return
        facts = [f.strip("- ").strip() for f in facts_text.split("\n") if f.strip().startswith("-")]
        for i, fact in enumerate(facts):
            if not fact:
                continue
            embedding = self.embedder.encode(fact).tolist()
            self.collection.add(
                ids=[f"{self.user_id}_{datetime.now().timestamp()}_{i}"],
                embeddings=[embedding],
                documents=[fact],
                metadatas=[{"user_id": self.user_id, "created_at": datetime.now().isoformat()}]
            )
        print(f"💾 Сохранено фактов: {len(facts)}")

    def recall(self, query, limit=5):
        if self.collection.count() == 0:
            return ""
        embedding = self.embedder.encode(query).tolist()
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(limit, self.collection.count()),
            where={"user_id": self.user_id}
        )
        if not results["documents"] or not results["documents"][0]:
            return ""
        return "\n".join(f"- {doc}" for doc in results["documents"][0])

    def get_all_memories(self):
        return self.collection.get(where={"user_id": self.user_id})["documents"]

    def _init_prospective_db(self):
        db_path = MEMORY_DIR / "prospective" / "reminders.db"
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT,
            text TEXT, remind_at TEXT, done INTEGER DEFAULT 0, created_at TEXT)""")
        self.db.commit()

    def add_reminder(self, text, remind_at):
        self.db.execute("INSERT INTO reminders (user_id,text,remind_at,created_at) VALUES (?,?,?,?)",
            (self.user_id, text, remind_at, datetime.now().isoformat()))
        self.db.commit()

    def get_pending_reminders(self):
        return self.db.execute(
            "SELECT id,text,remind_at FROM reminders WHERE user_id=? AND done=0",
            (self.user_id,)).fetchall()

    def _init_profile(self):
        self.profile_path = MEMORY_DIR / "profiles" / f"{self.user_id}.json"
        if not self.profile_path.exists():
            self._save_profile({"user_id":self.user_id,"name":self.user_id,
                "language":"ru","role":"owner","preferences":{},
                "created_at":datetime.now().isoformat()})

    def get_profile(self):
        with open(self.profile_path) as f:
            return json.load(f)

    def update_profile(self, updates):
        profile = self.get_profile()
        profile.update(updates)
        self._save_profile(profile)

    def _save_profile(self, data):
        with open(self.profile_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_skills(self):
        skills_dir = BASE_DIR / "skills"
        skill_texts = []
        for skill_file in sorted(skills_dir.rglob("SKILL.md")):
            parts = skill_file.read_text().split("---")
            if len(parts) >= 3:
                skill_texts.append(parts[2].strip())
        return "\n\n---\n\n".join(skill_texts)

if __name__ == "__main__":
    m = MeowBotMemory(user_id="vladimir")
    print("\n📝 Тест: сохраняем разговор...")
    m.remember([
        {"role":"user","content":"Меня зовут Владимир, я живу в Казани"},
        {"role":"assistant","content":"Мур! Запомнил, Владимир из Казани!"}
    ])
    print("\n🔍 Тест: вспоминаем...")
    print(m.recall("как зовут хозяина"))
    print("\n👤 Профиль:")
    print(json.dumps(m.get_profile(), ensure_ascii=False, indent=2))
    print("\n✅ Memory Manager работает!")
