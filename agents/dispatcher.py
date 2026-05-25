"""
Agent Dispatcher - handles all PC actions.
Each action speaks a short confirmation then acts.
"""
import os
import sys
import subprocess
import webbrowser
import threading
import time
import schedule
from pathlib import Path
from core.config_loader import load_config

_cfg     = load_config()
CODE_DIR = Path(_cfg["agentic"]["code_output_dir"])
CODE_DIR.mkdir(parents=True, exist_ok=True)


class AgentDispatcher:
    def __init__(self, tts, llm):
        self.tts      = tts
        self.llm      = llm
        self._reminders = []
        self._start_scheduler()

    def dispatch(self, intent: dict, lang: str = "en") -> bool:
        action = intent.get("action", "")
        params = intent.get("params", {})

        mapping = {
            "restart_pc":     self._restart,
            "shutdown_pc":    self._shutdown,
            "open_browser":   self._open_browser,
            "search_web":     self._search_web,
            "open_file":      self._open_file,
            "open_folder":    self._open_folder,
            "create_file":    self._create_file,
            "create_folder":  self._create_folder,
            "write_code":     self._write_code,
            "run_code":       self._run_code,
            "set_reminder":   self._set_reminder,
            "create_ppt":     self._create_ppt,
            "research_topic": self._research_topic,
            "system_info":    self._system_info,
        }

        fn = mapping.get(action)
        if fn:
            threading.Thread(target=fn, args=(params, lang), daemon=True).start()
            return True
        return False

    # ------------------------------------------------------------------ PC
    def _restart(self, p, lang):
        self.tts.speak("Restarting in 5 seconds.", lang)
        time.sleep(5)
        os.system("shutdown /r /t 0" if sys.platform=="win32" else "sudo reboot")

    def _shutdown(self, p, lang):
        self.tts.speak("Shutting down now.", lang)
        time.sleep(3)
        os.system("shutdown /s /t 0" if sys.platform=="win32" else "sudo shutdown now")

    # ------------------------------------------------------------------ Browser
    def _open_browser(self, p, lang):
        url = p.get("url", "https://www.google.com")
        if not url.startswith("http"):
            url = "https://" + url
        self.tts.speak("Opening that now.", lang)
        webbrowser.open(url)

    def _search_web(self, p, lang):
        query = p.get("query", "")
        url   = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        self.tts.speak(f"Searching for {query}.", lang)
        webbrowser.open(url)

    # ------------------------------------------------------------------ Files
    def _open_file(self, p, lang):
        path = p.get("path", "")
        if Path(path).exists():
            self.tts.speak("Opening that file.", lang)
            if sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path])
        else:
            self.tts.speak("File not found.", lang)

    def _open_folder(self, p, lang):
        path = p.get("path", str(Path.home()))
        self.tts.speak("Opening folder.", lang)
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.run(["xdg-open", path])

    def _create_file(self, p, lang):
        path = Path(p.get("path", "new_file.txt"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(p.get("content", ""), encoding="utf-8")
        self.tts.speak(f"Created {path.name}.", lang)

    def _create_folder(self, p, lang):
        path = Path(p.get("path", "new_folder"))
        path.mkdir(parents=True, exist_ok=True)
        self.tts.speak("Folder created.", lang)

    # ------------------------------------------------------------------ Code
    def _ext(self, lang):
        return {"python":"py","go":"go","javascript":"js","java":"java","rust":"rs"}.get(lang,"txt")

    def _write_code(self, p, lang):
        task     = p.get("task", "")
        code_lang= p.get("language", "python")
        filename = p.get("filename", f"solution.{self._ext(code_lang)}")

        self.tts.speak(f"Writing {code_lang} code for you.", lang)

        prompt = (f"Write clean {code_lang} code for: {task}\n"
                  f"Return ONLY the code. No explanation. No markdown fences.")
        code = ""
        for token in self.llm.chat_stream(prompt, language="en"):
            code += token

        # Strip markdown
        if "```" in code:
            lines = code.split("\n")
            code  = "\n".join(l for l in lines if not l.strip().startswith("```"))

        fpath = CODE_DIR / filename
        fpath.write_text(code, encoding="utf-8")
        self.llm.memory.store_code(code, code_lang, task)

        try:
            editor = _cfg["agentic"]["editor"]
            subprocess.Popen([editor, str(fpath)])
        except Exception:
            pass

        self.tts.speak(f"Done. Saved as {filename} and opened in your editor.", lang)

    def _run_code(self, p, lang):
        path     = p.get("path", "")
        code_lang= p.get("language", "python")
        cmds     = {"python":["python",path],"go":["go","run",path],"node":["node",path]}
        cmd      = cmds.get(code_lang, ["python", path])
        self.tts.speak("Running it now.", lang)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            out    = (result.stdout or result.stderr or "No output.").strip()[:200]
            self.tts.speak(f"Output: {out}", lang)
        except Exception as e:
            self.tts.speak(f"Error running code: {str(e)[:60]}", lang)

    # ------------------------------------------------------------------ Reminder
    def _set_reminder(self, p, lang):
        message = p.get("message", "reminder")
        minutes = int(p.get("minutes", 5))

        def remind():
            self.tts.speak(f"Reminder: {message}", lang)

        timer = threading.Timer(minutes * 60, remind)
        timer.daemon = True
        timer.start()
        self._reminders.append(timer)

        if minutes == 1:
            time_str = "1 minute"
        else:
            time_str = f"{minutes} minutes"
        self.tts.speak(f"Reminder set. I will remind you about {message} in {time_str}.", lang)

    def _start_scheduler(self):
        def run():
            while True:
                schedule.run_pending()
                time.sleep(10)
        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------ PPT
    def _create_ppt(self, p, lang):
        topic  = p.get("topic", "Presentation")
        slides = int(p.get("slides", 5))
        self.tts.speak(f"Creating a presentation on {topic}. Give me a moment.", lang)

        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
        except ImportError:
            self.tts.speak("PowerPoint library not installed. Run: pip install python-pptx", lang)
            return

        # Ask LLM for slide content
        prompt = (
            f"Create {slides} PowerPoint slides on: {topic}\n"
            f"Return ONLY a JSON list like this:\n"
            f'[{{"title": "Slide title", "content": "2-3 bullet points as text"}}]\n'
            f"No markdown. No extra text. Just the JSON array."
        )
        raw = ""
        for token in self.llm.chat_stream(prompt, language="en"):
            raw += token

        # Parse slide data
        try:
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            slides_data = __import__("json").loads(raw[start:end])
        except Exception:
            slides_data = [
                {"title": topic, "content": "Overview of the topic"},
                {"title": "Key Points", "content": "Main ideas and concepts"},
                {"title": "Details", "content": "In-depth analysis"},
                {"title": "Examples", "content": "Real-world applications"},
                {"title": "Summary", "content": "Conclusion and next steps"},
            ]

        prs = Presentation()
        # Title slide
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = topic
        if slide.placeholders[1]:
            slide.placeholders[1].text = f"Presented by {self.llm.user_id}"

        # Content slides
        for sd in slides_data:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = sd.get("title", "")
            tf = slide.placeholders[1].text_frame
            tf.text = sd.get("content", "")

        out_path = CODE_DIR / f"{topic.replace(' ','_')}.pptx"
        prs.save(str(out_path))

        try:
            os.startfile(str(out_path))
        except Exception:
            pass

        self.tts.speak(f"Done. Presentation on {topic} is ready and opened.", lang)

    # ------------------------------------------------------------------ Research
    def _research_topic(self, p, lang):
        topic = p.get("topic", "")
        self.tts.speak(f"Researching {topic} now. Give me a moment.", lang)

        def do_research():
            try:
                import urllib.request
                import urllib.parse
                # Search DuckDuckGo instant answers API (no key needed)
                query   = urllib.parse.quote(topic)
                url     = f"https://api.duckduckgo.com/?q={query}&format=json&no_redirect=1"
                req     = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
                resp    = urllib.request.urlopen(req, timeout=10)
                data    = __import__("json").loads(resp.read().decode("utf-8"))

                abstract = data.get("AbstractText", "")
                answer   = data.get("Answer", "")
                summary  = abstract or answer or ""

                if summary and len(summary) > 50:
                    # Store in knowledge base
                    self.llm.memory.sessions.add(
                        documents=[f"Research on {topic}: {summary[:1000]}"],
                        metadatas=[{"topic": topic, "source": "duckduckgo"}],
                        ids=[f"research_{topic.replace(' ','_')}_{int(time.time())}"],
                    )
                    short = summary[:200].strip()
                    self.tts.speak(
                        f"Done. Here is what I found about {topic}: {short}. "
                        f"You can now ask me questions about it.", lang
                    )
                else:
                    # Fallback: LLM knowledge
                    prompt = (
                        f"Summarise what you know about: {topic}\n"
                        f"Reply in 3 sentences maximum. Plain text only."
                    )
                    summary_text = ""
                    for token in self.llm.chat_stream(prompt, "en"):
                        summary_text += token
                    # Store in memory
                    self.llm.memory.sessions.add(
                        documents=[f"Research on {topic}: {summary_text}"],
                        metadatas=[{"topic": topic, "source": "llm"}],
                        ids=[f"research_{topic.replace(' ','_')}_{int(time.time())}"],
                    )
                    self.tts.speak(
                        f"I have noted what I know about {topic}. "
                        f"You can now ask me questions about it.", lang
                    )
            except Exception as e:
                print(f"[Research] Error: {e}")
                self.tts.speak(f"I had trouble researching that. Try asking me directly.", lang)

        threading.Thread(target=do_research, daemon=True).start()

    # ------------------------------------------------------------------ System info
    def _system_info(self, p, lang):
        try:
            import psutil
            cpu  = psutil.cpu_percent(interval=1)
            ram  = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            self.tts.speak(
                f"CPU is at {cpu:.0f}%, RAM at {ram:.0f}%, disk at {disk:.0f}%.", lang
            )
        except Exception:
            self.tts.speak("Could not read system metrics.", lang)
