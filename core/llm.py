"""
LLM Engine - Smart provider selection:
1. Groq API (if GROQ_API_KEY set) - free, 500 req/day, 200ms response, no install needed
2. Ollama local (if running) - fully offline
3. Error message if neither available

Groq is FREE at: https://console.groq.com - get key in 2 minutes.
Models on Groq: llama-3.3-70b (best), mixtral-8x7b, gemma2-9b
These are much better than phi3.5 and respond in 200ms vs 30s.
"""
import json
import os
import urllib.request
import urllib.error
from core.config_loader import load_config
from core.memory import MemoryStore

_cfg = load_config()
MODEL   = _cfg["llm"]["model"]
OPTIONS = {
    "num_gpu":     int(_cfg["llm"].get("num_gpu", 0)),
    "num_predict": int(_cfg["llm"]["num_predict"]),
    "temperature": float(_cfg["llm"]["temperature"]),
    "num_ctx":     int(_cfg["llm"]["num_ctx"]),
}
PERSONALITY = _cfg["llm"]["personality"]

INTENT_SYSTEM = """Extract the user intent. Return ONLY valid JSON, no other text.

Format: {"action": "<action>", "params": {}}

Actions:
answer_question      - general chat
open_browser         - open website, params: {"url": "https://..."}
search_web           - google search, params: {"query": "..."}
open_file            - params: {"path": "..."}
open_folder          - params: {"path": "..."}
create_file          - params: {"path": "...", "content": ""}
create_folder        - params: {"path": "..."}
write_code           - params: {"language": "python", "task": "...", "filename": "main.py"}
run_code             - params: {"path": "...", "language": "python"}
set_reminder         - params: {"message": "...", "minutes": 5}
create_ppt           - params: {"topic": "...", "slides": 5}
research_topic       - params: {"topic": "..."}
analyze_file         - params: {"path": "..."}
system_info          - params: {}
restart_pc           - params: {}
shutdown_pc          - params: {}
create_teams_meeting - params: {"title": "...", "start": "HH:MM", "end": "HH:MM"}
check_email          - params: {"from": "email@address.com"}
send_email           - params: {"to": "...", "subject": "...", "body": "..."}
screen_analyze       - params: {}
update_model         - params: {}

Examples:
"open chrome" -> {"action": "open_browser", "params": {"url": "https://www.google.com"}}
"remind me in 10 minutes to call john" -> {"action": "set_reminder", "params": {"message": "call john", "minutes": 10}}
"create a teams meeting at 2pm title project sync" -> {"action": "create_teams_meeting", "params": {"title": "project sync", "start": "14:00", "end": "15:00"}}
"check latest email from boss@company.com" -> {"action": "check_email", "params": {"from": "boss@company.com"}}
"what is on my screen" -> {"action": "screen_analyze", "params": {}}
"update your model" -> {"action": "update_model", "params": {}}

Return only JSON."""


def _groq_available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def _ollama_available() -> bool:
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def _call_groq(messages: list, max_tokens: int = 150, temperature: float = 0.7) -> str:
    key   = os.environ.get("GROQ_API_KEY", "")
    model = "llama-3.3-70b-versatile"  # Best free Groq model
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
        }
    )
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _call_groq_stream(messages: list, max_tokens: int = 200, temperature: float = 0.7):
    """Stream from Groq API."""
    key   = os.environ.get("GROQ_API_KEY", "")
    model = "llama-3.3-70b-versatile"
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
        }
    )
    resp = urllib.request.urlopen(req, timeout=30)
    for line in resp:
        line = line.decode("utf-8").strip()
        if line.startswith("data: "):
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta
            except Exception:
                continue


class LLMEngine:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory  = MemoryStore(user_id)
        self.history = []
        self.use_groq  = _groq_available()
        self.use_ollama= _ollama_available()

        if self.use_groq:
            print("[LLM] Provider: Groq API (llama-3.3-70b) - fast cloud mode")
        elif self.use_ollama:
            print(f"[LLM] Provider: Ollama local ({MODEL})")
        else:
            print("[LLM] WARNING: No LLM provider available!")
            print("[LLM] Options:")
            print("[LLM]   A) Install Ollama from https://ollama.com")
            print("[LLM]   B) Get free Groq key from https://console.groq.com")
            print("[LLM]      Then set: GROQ_API_KEY=your_key in environment")

    def extract_intent(self, text: str) -> dict:
        msgs = [
            {"role": "system", "content": INTENT_SYSTEM},
            {"role": "user",   "content": text},
        ]
        try:
            if self.use_groq:
                raw = _call_groq(msgs, max_tokens=80, temperature=0.1)
            elif self.use_ollama:
                import ollama
                r   = ollama.chat(model=MODEL, messages=msgs,
                                  options={"num_predict": 80, "temperature": 0.1})
                raw = r["message"]["content"]
            else:
                return {"action": "answer_question", "params": {}}

            # Extract JSON
            raw = raw.strip()
            if "```" in raw:
                raw = re.sub(r"```[a-z]*\n?", "", raw).replace("```", "")
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except Exception as e:
            print(f"[LLM] Intent error: {e}")
        return {"action": "answer_question", "params": {}}

    def chat_stream(self, user_text: str, language: str = "en"):
        context = self.memory.get_context(user_text)
        system  = PERSONALITY
        if context:
            system += f"\n\nContext: {context}"
        if language not in ("en", "auto"):
            names  = {"ta": "Tamil", "hi": "Hindi"}
            system += f"\n\nRespond in {names.get(language, language)}."
        system += ("\n\nCRITICAL: Max 2-3 short sentences. No markdown. "
                   "No bullet points. No lists. Plain conversational speech only.")

        self.history.append({"role": "user", "content": user_text})
        messages = [{"role": "system", "content": system}] + self.history[-6:]

        full = ""
        try:
            if self.use_groq:
                for token in _call_groq_stream(messages, max_tokens=150):
                    full += token
                    yield token
            elif self.use_ollama:
                import ollama
                stream = ollama.chat(model=MODEL, messages=messages,
                                     stream=True, options=OPTIONS)
                for chunk in stream:
                    token = chunk["message"]["content"]
                    full += token
                    yield token
            else:
                msg = ("I need a language model to answer. "
                       "Please install Ollama from ollama.com "
                       "or set a GROQ_API_KEY environment variable.")
                yield msg
                full = msg
        except Exception as e:
            err = f"Sorry, LLM error: {str(e)[:40]}"
            yield err
            full = err

        self.history.append({"role": "assistant", "content": full})
        self.memory.log_turn(user_text, full, language=language)

    def simple_query(self, prompt: str) -> str:
        """Non-streaming single query for internal use."""
        msgs = [{"role": "user", "content": prompt}]
        try:
            if self.use_groq:
                return _call_groq(msgs, max_tokens=300)
            elif self.use_ollama:
                import ollama
                r = ollama.chat(model=MODEL, messages=msgs,
                                options={"num_predict": 300, "temperature": 0.3})
                return r["message"]["content"]
        except Exception as e:
            return f"Error: {e}"
        return "No LLM provider available."

    def rate_last(self, quality: float):
        self.memory.rate_last(quality)

    def reset(self):
        self.history = []


import re  # needed by extract_intent
