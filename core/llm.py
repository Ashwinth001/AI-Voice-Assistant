"""
LLM Engine - Ollama with strict short-reply enforcement.
No markdown, no lists, no follow-up questions.
"""
import json
import ollama
from core.config_loader import load_config
from core.memory import MemoryStore

_cfg = load_config()
MODEL    = _cfg["llm"]["model"]
OPTIONS  = {
    "num_gpu":     int(_cfg["llm"].get("num_gpu", 0)),
    "num_predict": int(_cfg["llm"]["num_predict"]),
    "temperature": float(_cfg["llm"]["temperature"]),
    "num_ctx":     int(_cfg["llm"]["num_ctx"]),
}
PERSONALITY = _cfg["llm"]["personality"]

INTENT_SYSTEM = """Extract the user intent from the message. Return ONLY valid JSON, nothing else.
No explanation, no markdown, just the JSON object.

Format: {"action": "<action>", "params": {}}

Actions:
answer_question    - general chat, knowledge questions
restart_pc         - restart or reboot computer
shutdown_pc        - shut down computer
open_browser       - open a website, params: {"url": "https://..."}
search_web         - search google, params: {"query": "..."}
open_file          - open a file, params: {"path": "..."}
open_folder        - open a folder, params: {"path": "..."}
create_file        - create a file, params: {"path": "...", "content": ""}
create_folder      - create a folder, params: {"path": "..."}
write_code         - write and open code, params: {"language": "python", "task": "...", "filename": "main.py"}
run_code           - run a code file, params: {"path": "...", "language": "python"}
set_reminder       - set a reminder, params: {"message": "...", "minutes": 5}
create_ppt         - create PowerPoint presentation, params: {"topic": "...", "slides": 5}
research_topic     - search internet and learn about topic, params: {"topic": "..."}
system_info        - check CPU, RAM, disk usage
play_music         - open music

If user says "open chrome" or "open google chrome", action is open_browser with url https://www.google.com
If user says "open [website]", action is open_browser with correct url
If user says "remind me in X minutes", action is set_reminder with minutes field
If user says "create a presentation/ppt on X", action is create_ppt
If user says "learn about X" or "research X", action is research_topic

Return only JSON. Example: {"action": "open_browser", "params": {"url": "https://www.google.com"}}"""


class LLMEngine:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory  = MemoryStore(user_id)
        self.history = []
        print(f"[LLM] Using model: {MODEL}")

    def extract_intent(self, text: str) -> dict:
        try:
            resp = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": INTENT_SYSTEM},
                    {"role": "user",   "content": text},
                ],
                options={"num_gpu": OPTIONS["num_gpu"], "num_predict": 80,
                         "temperature": 0.1},
            )
            raw = resp["message"]["content"].strip()
            # Strip any markdown fences
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            # Find the JSON object
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start >= 0 and end > start:
                raw = raw[start:end]
            return json.loads(raw)
        except Exception as e:
            print(f"[LLM] Intent parse error: {e}")
            return {"action": "answer_question", "params": {"query": text}}

    def chat_stream(self, user_text: str, language: str = "en"):
        """Stream response tokens. Short replies enforced by personality + system."""
        context = self.memory.get_context(user_text)

        system = PERSONALITY
        if context:
            system += f"\n\nContext from past: {context}"
        if language not in ("en", "auto"):
            lang_names = {"ta": "Tamil", "hi": "Hindi"}
            system += f"\n\nRespond in {lang_names.get(language, language)}."

        # Add strict reminder every time
        system += ("\n\nCRITICAL: Your entire reply must be under 3 sentences. "
                   "No markdown. No bullet points. No follow-up questions. "
                   "No lists. Plain conversational English only.")

        self.history.append({"role": "user", "content": user_text})
        messages = [{"role": "system", "content": system}] + self.history[-6:]

        full = ""
        try:
            stream = ollama.chat(
                model=MODEL,
                messages=messages,
                stream=True,
                options=OPTIONS,
            )
            for chunk in stream:
                token = chunk["message"]["content"]
                full  += token
                yield token
        except Exception as e:
            err = f"Sorry, I had a hiccup. {str(e)[:40]}"
            yield err
            full = err

        self.history.append({"role": "assistant", "content": full})
        self.memory.log_turn(user_text, full, language=language)

    def rate_last(self, quality: float):
        self.memory.rate_last(quality)

    def reset(self):
        self.history = []
