# -*- coding: utf-8 -*-
"""Self-learning brain: knowledge base, corrections, classification. No external models."""

import sqlite3
import json
import re
import os
import time
import threading
from typing import Optional
import config.settings as settings


class Brain:
    """Local-only learning: stores facts, corrections, vocabulary; classifies and retrieves."""

    def __init__(self):
        self.db_path = settings.KNOWLEDGE_DB
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._ensure_db()

    def _ensure_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                tag TEXT NOT NULL,
                source TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE(content, tag)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original TEXT NOT NULL,
                corrected TEXT NOT NULL,
                context TEXT,
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_or_phrase TEXT NOT NULL UNIQUE,
                meaning_or_response TEXT,
                language TEXT,
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_text TEXT NOT NULL,
                assistant_text TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def _tag_from_content(self, content: str) -> str:
        """Classify content into one of CLASSIFICATION_TAGS."""
        c = content.lower().strip()
        if any(c.startswith(x) for x in ("remember that", "don't forget", "note that")):
            return "fact"
        if any(x in c for x in ("i like", "i prefer", "i love", "i hate")):
            return "preference"
        if any(x in c for x in ("remind me", "alarm", "wake me")):
            return "reminder"
        if any(x in c for x in ("open", "close", "run", "start", "stop", "shut down")):
            return "command"
        if "?" in c or c.startswith(("what", "why", "how", "when", "where", "who")):
            return "question"
        if any(x in c for x in ("no that's wrong", "i meant", "correct that", "actually")):
            return "correction"
        if any(x in c for x in ("means", "definition of", "translate", "word for")):
            return "vocabulary"
        if any(x in c for x in ("in spanish", "in french", "language")):
            return "language"
        if any(x in c for x in ("scan", "virus", "dangerous", "block")):
            return "security"
        if any(x in c for x in ("system", "app", "process")):
            return "system"
        return "fact"

    def learn_fact(self, content: str, source: str = "voice") -> None:
        """Store a fact; tag is auto-classified."""
        tag = self._tag_from_content(content)
        now = time.time()
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO knowledge (content, tag, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (content.strip(), tag, source, now, now),
                )
                self._conn.commit()
        except Exception:
            pass

    def apply_correction(self, original: str, corrected: str, context: str = "") -> None:
        """Learn from user correction: 'I meant X' -> update knowledge and store correction."""
        now = time.time()
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO corrections (original, corrected, context, created_at) VALUES (?, ?, ?, ?)",
                    (original, corrected, context, now),
                )
                self._conn.execute(
                    "UPDATE knowledge SET content = ?, updated_at = ? WHERE content = ?",
                    (corrected, now, original),
                )
                self._conn.commit()
        except Exception:
            pass

    def learn_vocabulary(self, word_or_phrase: str, meaning_or_response: str, language: str = "") -> None:
        """Store new word/phrase and its meaning or response."""
        now = time.time()
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO vocabulary (word_or_phrase, meaning_or_response, language, created_at) VALUES (?, ?, ?, ?)",
                    (word_or_phrase.strip(), meaning_or_response.strip(), language, now),
                )
                self._conn.commit()
        except Exception:
            pass

    def set_preference(self, key: str, value: str) -> None:
        """Store a preference (e.g. response_language = tamil)."""
        now = time.time()
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
                    (key.strip(), value.strip(), now),
                )
                self._conn.commit()
        except Exception:
            pass

    def get_preference(self, key: str) -> Optional[str]:
        """Get a stored preference, or None."""
        try:
            with self._lock:
                row = self._conn.execute(
                    "SELECT value FROM preferences WHERE key = ?", (key.strip(),)
                ).fetchone()
                return row[0] if row else None
        except Exception:
            return None

    def store_conversation(self, user_text: str, assistant_text: str) -> None:
        """Store one turn for learning from context."""
        now = time.time()
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO conversations (user_text, assistant_text, created_at) VALUES (?, ?, ?)",
                    (user_text, assistant_text, now),
                )
                self._conn.commit()
        except Exception:
            pass

    def get_corrected(self, text: str) -> Optional[str]:
        """If user previously corrected this phrase, return the corrected version."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT corrected FROM corrections WHERE original = ? ORDER BY created_at DESC LIMIT 1",
                (text.strip(),),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def get_vocabulary(self, word_or_phrase: str) -> Optional[str]:
        """Return stored meaning/response for word/phrase."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT meaning_or_response FROM vocabulary WHERE LOWER(word_or_phrase) = LOWER(?) LIMIT 1",
                (word_or_phrase.strip(),),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def search_knowledge(self, query: str, tag: Optional[str] = None, limit: int = 5) -> list[tuple[str, str]]:
        """Simple keyword search in knowledge (no external embeddings). Returns (content, tag)."""
        words = re.findall(r"\w+", query.lower())
        if not words:
            return []
        placeholders = " OR ".join(["content LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words]
        sql = f"SELECT content, tag FROM knowledge WHERE ({placeholders})"
        if tag:
            sql += " AND tag = ?"
            params.append(tag)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    def get_response_candidates(self, user_text: str) -> list[str]:
        """Build response candidates from corrections, vocabulary, and knowledge."""
        candidates = []
        corrected = self.get_corrected(user_text)
        if corrected:
            candidates.append(f"I'll remember: {corrected}")
        vocab = self.get_vocabulary(user_text)
        if vocab:
            candidates.append(vocab)
        for content, tag in self.search_knowledge(user_text, limit=3):
            candidates.append(content)
        return candidates

    def get_recent_conversations(self, limit: int = 10) -> list[tuple[str, str]]:
        """Return recent (user_text, assistant_text) for LLM context."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT user_text, assistant_text FROM conversations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        return list(reversed(rows))  # chronological order

    def get_knowledge_context_for_llm(self, query: str = "", limit: int = 15) -> str:
        """Return a short text block of relevant knowledge for the LLM system prompt."""
        if query.strip():
            results = self.search_knowledge(query, limit=limit)
        else:
            with self._lock:
                cur = self._conn.execute(
                    "SELECT content, tag FROM knowledge ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                )
                results = cur.fetchall()
        if not results:
            return ""
        lines = [f"- {content}" for content, _ in results]
        return "Things you know (use when relevant):\n" + "\n".join(lines)

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
