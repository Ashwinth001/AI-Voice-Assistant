# -*- coding: utf-8 -*-
"""Local LLM (Ollama) for human-like thinking and conversation."""

from typing import Optional

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

import config.settings as settings

# Default model; user can pull with: ollama pull llama3.2
DEFAULT_MODEL = getattr(settings, "OLLAMA_MODEL", "llama3.2")


SYSTEM_PROMPT = """You are the owner's personal voice assistant and friend. Do what they want; learn from everything they say.
- Keep replies short (1-3 sentences) for voice—no long paragraphs.
- Be conversational and human: warm, natural, with a light sense of humor when it fits.
- Answer questions directly. If you don't know, say so in a friendly way and remember what they said for next time.
- Use "Things you know" when it fits. You only obey the owner. Be helpful, casual, and like a friend—not a stiff assistant. Always try to do what they asked; if you can't, say what you did instead and remember it."""


class LocalLLM:
    """Uses Ollama (local) for chat. Thinks and responds like a human."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._available = False
        if OLLAMA_AVAILABLE:
            self._check_ollama()

    def _check_ollama(self) -> bool:
        try:
            ollama.list()
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def is_available(self) -> bool:
        return self._available and OLLAMA_AVAILABLE

    def chat(
        self,
        user_message: str,
        knowledge_context: str = "",
        recent_conversations: Optional[list[tuple[str, str]]] = None,
    ) -> str:
        """
        Get a human-like reply from the local LLM.
        knowledge_context: text block of facts/preferences from the brain.
        recent_conversations: list of (user_text, assistant_text) for context.
        """
        if not self.is_available():
            return ""

        system = SYSTEM_PROMPT
        if knowledge_context.strip():
            system = system.rstrip() + "\n\n" + knowledge_context.strip()

        messages = [{"role": "system", "content": system}]
        if recent_conversations:
            for u, a in recent_conversations[-10:]:  # last 10 turns
                if u.strip():
                    messages.append({"role": "user", "content": u})
                if a.strip():
                    messages.append({"role": "assistant", "content": a})
        messages.append({"role": "user", "content": user_message})

        try:
            response = ollama.chat(model=self.model, messages=messages)
            content = (response.get("message") or {}).get("content") or ""
            return content.strip()
        except Exception:
            return ""

    def parse_intent(self, user_message: str) -> Optional[dict]:
        """
        Ask the LLM what the user wanted from possibly garbled/misheard speech.
        Returns intent dict: open, note, search, open_url, remind, time, date, calculate, or chat/None.
        """
        if not self.is_available() or not (user_message or "").strip():
            return None
        prompt = (
            "The user said this (possibly misheard): \"%s\"\n\n"
            "What did they want? Reply with exactly ONE line:\n"
            "- OPEN <app or site> if they want to open an app or website (e.g. OPEN chrome, OPEN word, OPEN youtube)\n"
            "- NOTE <content> if they want to add a note (e.g. NOTE buy milk)\n"
            "- SEARCH <query> if they want to search the web (e.g. SEARCH time travel)\n"
            "- SEARCH_YOUTUBE <query> if they want to search on YouTube (e.g. SEARCH_YOUTUBE dhoom 3)\n"
            "- OPEN_PATH <path> if they want to open a folder path (e.g. OPEN_PATH D:\\\\Videos\\\\Movies)\n"
            "- LEARN_LANGUAGE <language> if they want to learn a language (e.g. LEARN_LANGUAGE french)\n"
            "- REMIND <content> if they want a reminder (e.g. REMIND call mom tomorrow)\n"
            "- TIME if they want the current time\n"
            "- DATE if they want today's date\n"
            "- CALCULATE <expression> if they want math (e.g. CALCULATE 15*23)\n"
            "- CHAT if they are just talking or asking something else\n"
            "If unclear, reply CHAT."
        ) % (user_message.strip()[:300],)
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = ((response.get("message") or {}).get("content") or "").strip()
            content_upper = raw.upper()
            if "OPEN " in content_upper:
                idx = content_upper.index("OPEN ") + 5
                app = raw[idx:].split("\n")[0].strip()
                if app:
                    return {"intent": "open", "app": app.lower()}
            if "NOTE " in content_upper:
                idx = content_upper.index("NOTE ") + 5
                note = raw[idx:].split("\n")[0].strip()
                if note:
                    return {"intent": "note", "content": note}
            if "SEARCH " in content_upper:
                idx = content_upper.index("SEARCH ") + 7
                query = raw[idx:].split("\n")[0].strip()
                if query:
                    return {"intent": "search", "query": query}
            if "REMIND " in content_upper:
                idx = content_upper.index("REMIND ") + 7
                content = raw[idx:].split("\n")[0].strip()
                if content:
                    return {"intent": "remind", "content": content}
            if content_upper.startswith("TIME") or content_upper.strip() == "TIME":
                return {"intent": "time"}
            if content_upper.startswith("DATE") or content_upper.strip() == "DATE":
                return {"intent": "date"}
            if "CALCULATE " in content_upper:
                idx = content_upper.index("CALCULATE ") + 10
                expr = raw[idx:].split("\n")[0].strip().replace(" ", "")
                if expr and all(c in "0123456789+-*/.()" for c in expr):
                    return {"intent": "calculate", "expr": expr}
            if "SEARCH_YOUTUBE " in content_upper:
                idx = content_upper.index("SEARCH_YOUTUBE ") + 15
                query = raw[idx:].split("\n")[0].strip()
                if query:
                    return {"intent": "search_youtube", "query": query}
            if "OPEN_PATH " in content_upper:
                idx = content_upper.index("OPEN_PATH ") + 10
                path = raw[idx:].split("\n")[0].strip().replace("/", "\\")
                if path:
                    return {"intent": "open_path", "path": path}
            if "LEARN_LANGUAGE " in content_upper:
                idx = content_upper.index("LEARN_LANGUAGE ") + 15
                lang = raw[idx:].split("\n")[0].strip()
                if lang:
                    return {"intent": "learn_language", "lang": lang}
        except Exception:
            pass
        return None
