"""
Memory - ChromaDB per-user persistent store.
Fixed: all file writes use utf-8 encoding explicitly.
"""
import chromadb
import json
import datetime
import uuid
from pathlib import Path
from core.config_loader import load_config

_cfg    = load_config()
TOP_K   = int(_cfg["memory"]["top_k_results"])
DB_PATH = Path(_cfg["memory"]["chroma_path"])


class MemoryStore:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.client  = chromadb.PersistentClient(path=str(DB_PATH))
        self.sessions  = self.client.get_or_create_collection(f"{user_id}_sessions")
        self.knowledge = self.client.get_or_create_collection(f"{user_id}_knowledge")
        self.code_col  = self.client.get_or_create_collection(f"{user_id}_code")
        self._last_id  = None
        print(f"[Memory] Loaded for user: {user_id}")

    def get_context(self, query: str) -> str:
        parts = []
        try:
            n = min(TOP_K, self.sessions.count())
            if n > 0:
                r = self.sessions.query(query_texts=[query], n_results=n)
                parts += r["documents"][0]
        except Exception:
            pass
        try:
            n = min(3, self.knowledge.count())
            if n > 0:
                r = self.knowledge.query(query_texts=[query], n_results=n)
                parts += r["documents"][0]
        except Exception:
            pass
        return " | ".join(parts[:4]) if parts else ""

    def log_turn(self, user_text: str, response: str,
                 language: str = "en", quality: float = 0.7):
        tid = f"{self.user_id}_{uuid.uuid4().hex[:8]}"
        doc = f"User: {user_text}\nAssistant: {response}"
        meta = {
            "timestamp": datetime.datetime.now().isoformat(),
            "language":  language,
            "quality":   quality,
            "user_id":   self.user_id,
        }
        try:
            self.sessions.add(documents=[doc], metadatas=[meta], ids=[tid])
        except Exception:
            pass
        self._last_id = tid
        self._write_jsonl(user_text, response, language, quality, tid)

    def rate_last(self, quality: float):
        if self._last_id:
            try:
                self.sessions.update(ids=[self._last_id],
                                     metadatas=[{"quality": quality}])
            except Exception:
                pass

    def ingest_document(self, file_path: str, topic: str):
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                text = " ".join(p.extract_text() or "" for p in pdf.pages)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")

        chunk_size, overlap = 500, 100
        chunks, i = [], 0
        while i < len(text):
            chunks.append(text[i:i+chunk_size])
            i += chunk_size - overlap

        ids   = [f"{self.user_id}_{topic}_{j}" for j in range(len(chunks))]
        metas = [{"topic": topic, "source": str(path)}] * len(chunks)
        try:
            self.knowledge.upsert(documents=chunks, metadatas=metas, ids=ids)
            print(f"[Memory] Ingested {len(chunks)} chunks: {path.name}")
        except Exception as e:
            print(f"[Memory] Ingest error: {e}")

    def store_code(self, code: str, language: str, task: str):
        cid = f"{self.user_id}_code_{uuid.uuid4().hex[:8]}"
        try:
            self.code_col.add(
                documents=[code],
                metadatas=[{"language": language, "task": task}],
                ids=[cid],
            )
        except Exception:
            pass

    def _write_jsonl(self, user_text, response, language, quality, tid):
        data_path = Path(_cfg["training"]["data_path"])
        data_path.mkdir(parents=True, exist_ok=True)
        entry = {
            "id":        tid,
            "timestamp": datetime.datetime.now().isoformat(),
            "language":  language,
            "quality":   quality,
            "messages": [
                {"role": "user",      "content": user_text},
                {"role": "assistant", "content": response},
            ],
        }
        fpath = data_path / f"{self.user_id}_sessions.jsonl"
        # IMPORTANT: explicit utf-8 encoding to prevent Windows cp1252 errors
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def session_count(self):
        try:
            return self.sessions.count()
        except Exception:
            return 0

    def knowledge_count(self):
        try:
            return self.knowledge.count()
        except Exception:
            return 0
