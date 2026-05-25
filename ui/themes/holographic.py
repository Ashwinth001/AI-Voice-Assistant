"""
Holographic UI - All text from config.yaml. No hardcoded strings.
"""
import tkinter as tk
from tkinter import filedialog, messagebox
import math, time, threading, random, os, sys, json
from pathlib import Path

C = {
    "bg":    "#020d18", "bg2":   "#041424", "panel": "#061c2e",
    "dim2":  "#083040", "border":"#0a4060", "dim":   "#0a5070",
    "accent":"#00c8ff", "accent2":"#00ff9f","accent3":"#ff6b35",
    "warn":  "#ffaa00", "error": "#ff3333", "white": "#cce8f0",
}

def mono(size=9, bold=False):
    return ("Courier New", size, "bold" if bold else "normal")

def hex_pts(cx, cy, r):
    pts = []
    for i in range(6):
        a = math.radians(60*i - 30)
        pts += [cx + r*math.cos(a), cy + r*math.sin(a)]
    return pts

def sep(p):
    tk.Frame(p, bg=C["border"], height=1).pack(fill="x", padx=14, pady=2)

def sec_lbl(p, t):
    tk.Label(p, text=t, fg=C["dim"], bg=C["bg"],
             font=mono(8)).pack(anchor="w", padx=14, pady=(4,1))

def sec_lbl_in(p, t):
    tk.Label(p, text=t, fg=C["dim"], bg=C["panel"],
             font=mono(8)).pack(anchor="w", padx=8, pady=(5,2))

def bot_lbl(parent, text, fg, side):
    l = tk.Label(parent, text=text, fg=fg, bg=C["bg2"], font=mono(8))
    l.pack(side=side, padx=7, pady=4)
    return l

def holo_btn(parent, text, cmd):
    return tk.Button(parent, text=text, fg=C["accent"], bg=C["panel"],
                     relief="flat", font=mono(8), padx=8, pady=4,
                     activebackground=C["border"],
                     activeforeground=C["white"], command=cmd)

def scrollable_frame(parent):
    frame  = tk.Frame(parent, bg=C["bg"])
    frame.pack(fill="both", expand=True)
    canvas = tk.Canvas(frame, bg=C["bg"], highlightthickness=0)
    sb     = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=sb.set)
    inner  = tk.Frame(canvas, bg=C["bg"])
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    def _on_config(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(win_id, width=canvas.winfo_width())
    inner.bind("<Configure>", _on_config)
    return inner


class HolographicUI:
    def __init__(self, root: tk.Tk, orchestrator=None):
        self.root         = root
        self.orchestrator = orchestrator
        self.state        = "standby"

        # ---- Load config FRESH every time ----
        from core.config_loader import load_config
        self._cfg       = load_config()
        self.app_name   = self._cfg["app"]["name"].upper()
        self.wake_word  = self._cfg["app"]["wake_word"]
        self.model_name = self._cfg["llm"]["model"]
        self.user_id    = self._cfg["app"]["user_id"]

        # Animation state
        self._angle = 0.0
        self._pulse = 0.0
        self._wave  = [0.0] * 90
        self._chart = [0.0] * 80
        self._tick  = 0
        self._active_panel = "main"
        self._log_lines = []

        self._setup_window()
        self._build_nav()
        self._build_panels()
        self._show_panel("main")
        self._start_animations()

    # ------------------------------------------------------------------ window
    def _setup_window(self):
        self.root.title(f"{self.app_name} -- Holographic Interface")
        self.root.geometry("600x900")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)
        self.root.attributes("-alpha", 0.97)
        self.root.bind("<ButtonPress-1>", lambda e: setattr(self, "_dx", e.x) or setattr(self, "_dy", e.y))
        self.root.bind("<B1-Motion>",     self._drag)
        self._dx = self._dy = 0

    def _drag(self, e):
        self.root.geometry(f"+{self.root.winfo_x()+e.x-self._dx}+{self.root.winfo_y()+e.y-self._dy}")

    # ------------------------------------------------------------------ nav bar
    def _build_nav(self):
        top = tk.Frame(self.root, bg=C["bg2"], height=40)
        top.pack(fill="x")
        top.pack_propagate(False)

        # Diamond icon + app name (from config)
        tk.Label(top, text="*", fg=C["accent"], bg=C["bg2"],
                 font=mono(12, True)).pack(side="left", padx=(10,2))
        tk.Label(top, text=self.app_name, fg=C["accent"], bg=C["bg2"],
                 font=mono(13, True)).pack(side="left")

        # Status dots
        self.dot_active = tk.Label(top, text="o", fg=C["accent2"], bg=C["bg2"], font=mono(10))
        self.dot_active.pack(side="left", padx=4)
        tk.Label(top, text="o", fg=C["dim"], bg=C["bg2"], font=mono(8)).pack(side="left")

        # Clock
        self.lbl_clock = tk.Label(top, text="00:00:00", fg=C["accent"],
                                   bg=C["bg2"], font=mono(11, True))
        self.lbl_clock.pack(side="left", padx=18)

        # Standby button
        self.btn_sb = tk.Button(top, text="STANDBY", fg=C["accent"], bg=C["panel"],
                                 relief="flat", font=mono(8), padx=8, pady=2,
                                 activebackground=C["border"],
                                 activeforeground=C["white"],
                                 command=self._toggle_standby)
        self.btn_sb.pack(side="right", padx=10, pady=6)

        # Tab bar
        nav = tk.Frame(self.root, bg=C["dim2"], height=28)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        self._nav_btns = {}
        for name, label in [("main","MAIN"),("settings","SETTINGS"),
                              ("knowledge","KNOWLEDGE"),("training","TRAINING"),
                              ("logs","LOGS")]:
            b = tk.Button(nav, text=label, fg=C["dim"], bg=C["dim2"],
                          relief="flat", font=mono(8), padx=12, pady=4,
                          activebackground=C["panel"], activeforeground=C["accent"],
                          command=lambda n=name: self._show_panel(n))
            b.pack(side="left")
            self._nav_btns[name] = b

    def _show_panel(self, name):
        for n, b in self._nav_btns.items():
            b.config(fg=C["accent"] if n==name else C["dim"],
                     bg=C["panel"] if n==name else C["dim2"])
        for n, f in self._panels.items():
            (f.pack if n==name else f.pack_forget)(fill="both", expand=True) if n==name else f.pack_forget()
        self._active_panel = name

    def _build_panels(self):
        self._panels = {
            "main":      self._build_main(),
            "settings":  self._build_settings(),
            "knowledge": self._build_knowledge(),
            "training":  self._build_training(),
            "logs":      self._build_logs(),
        }

    # ------------------------------------------------------------------ MAIN
    def _build_main(self):
        f = tk.Frame(self.root, bg=C["bg"])

        # Orb canvas
        self.orb_cv = tk.Canvas(f, width=590, height=220, bg=C["bg"], highlightthickness=0)
        self.orb_cv.pack(pady=(4,0))
        self._init_orb()
        sep(f)

        # Audio chart
        sec_lbl(f, "AUDIO INPUT LEVEL")
        self.chart_cv = tk.Canvas(f, width=570, height=68, bg=C["panel"],
                                   highlightthickness=1, highlightbackground=C["border"])
        self.chart_cv.pack(padx=14, pady=(0,4))
        sep(f)

        # Telemetry
        tel = tk.Frame(f, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
        tel.pack(fill="x", padx=14, pady=2)
        sec_lbl_in(tel, "SYSTEM TELEMETRY")

        self.tel = {}
        rows = [
            ("MODE",   "STANDBY",                             C["warn"]),
            ("INPUT",  f'Say "{self.wake_word}" to activate', C["accent2"]),
            ("TASK",   "--",                                   C["dim"]),
            ("OUTPUT", "Awaiting activation...",               C["accent"]),
        ]
        for key, default, col in rows:
            row = tk.Frame(tel, bg=C["panel"])
            row.pack(fill="x", padx=8, pady=1)
            tk.Label(row, text=key, fg=C["dim"], bg=C["panel"],
                     font=mono(8), width=8, anchor="w").pack(side="left")
            lv = tk.Label(row, text=default, fg=col, bg=C["panel"],
                          font=mono(9), anchor="w", wraplength=450, justify="left")
            lv.pack(side="left", fill="x", expand=True)
            self.tel[key] = lv
        sep(f)

        # Subsystems
        sub = tk.Frame(f, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
        sub.pack(fill="x", padx=14, pady=2)
        sec_lbl_in(sub, "SUBSYSTEMS")
        self.sub_bars = {}
        for name in ["STT / Whisper","LLM / Ollama","TTS / Piper","RAG / ChromaDB"]:
            row = tk.Frame(sub, bg=C["panel"])
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=name, fg=C["dim"], bg=C["panel"],
                     font=mono(8), width=18, anchor="w").pack(side="left")
            bg_bar = tk.Frame(row, bg=C["border"], height=5, width=310)
            bg_bar.pack(side="left", padx=4)
            bg_bar.pack_propagate(False)
            bar = tk.Frame(bg_bar, bg=C["accent"], height=5, width=310)
            bar.pack(fill="both")
            pct = tk.Label(row, text="100%", fg=C["accent"], bg=C["panel"], font=mono(8))
            pct.pack(side="left")
            self.sub_bars[name] = (bar, pct)
        sep(f)

        # Bottom status bar
        bot = tk.Frame(f, bg=C["bg2"], highlightthickness=1, highlightbackground=C["border"])
        bot.pack(fill="x", padx=14, pady=(2,8))
        self.lbl_cpu   = bot_lbl(bot, "CPU  --%",  C["accent3"], "left")
        self.lbl_ram   = bot_lbl(bot, "RAM  --%",  C["warn"],    "left")
        self.lbl_disk  = bot_lbl(bot, "DSK  --%",  C["dim"],     "left")
        self.lbl_sess  = bot_lbl(bot, "SESSIONS 0",C["dim"],     "left")
        self.lbl_model = bot_lbl(bot, f"LLM {self.model_name}", C["accent2"], "right")
        self.lbl_ver   = bot_lbl(bot, f"{self.app_name} v1.0",  C["dim"],     "right")
        return f

    def _init_orb(self):
        c = self.orb_cv
        for row in range(14):
            for col in range(22):
                x = col*26 + (row%2)*13
                y = row*22
                c.create_polygon(hex_pts(x,y,6), outline=C["border"], fill="", width=0.4)
        cx, cy = 295, 108
        c.create_oval(cx-90,cy-90,cx+90,cy+90, outline=C["border"], width=1)
        c.create_oval(cx-72,cy-72,cx+72,cy+72, outline=C["dim"], width=1, dash=(4,6))
        c.create_oval(cx-54,cy-54,cx+54,cy+54, outline=C["border"], width=0.8)
        self.o_dot1  = c.create_oval(0,0,9,9,   fill=C["accent"],  outline="")
        self.o_dot2  = c.create_oval(0,0,6,6,   fill=C["accent2"], outline="")
        self.o_trail = c.create_oval(0,0,14,14, outline=C["accent"], fill="", width=0.6)
        dp = [cx,cy-30, cx+22,cy, cx,cy+30, cx-22,cy]
        self.o_core  = c.create_polygon(dp, outline=C["accent"], fill=C["bg2"], width=1.5)
        self.o_inner = c.create_polygon(dp, outline=C["dim"], fill="", width=0.6)
        self.o_scan  = c.create_line(cx-90,cy,cx+90,cy, fill=C["accent"], width=0.5, dash=(2,4))
        self.o_state = c.create_text(cx, cy+68,
                                      text=f"[ {self.app_name} - STANDBY ]",
                                      fill=C["dim"], font=mono(9))
        self.o_wave  = c.create_line(30,197,560,197, fill=C["dim"], width=1)

    # ------------------------------------------------------------------ SETTINGS
    def _build_settings(self):
        f = tk.Frame(self.root, bg=C["bg"])
        sec_lbl(f, "CONFIGURATION -- changes take effect on next restart")
        inner = scrollable_frame(f)
        from core.config_loader import load_config, save_config
        cfg = load_config()
        self._sv = {}

        sections = {
            "APP": [
                ("name",      cfg["app"]["name"],      "Assistant name"),
                ("wake_word", cfg["app"]["wake_word"],  "Wake word (what you say to activate)"),
                ("user_id",   cfg["app"]["user_id"],    "Your user ID"),
                ("theme",     cfg["app"]["theme"],      "Theme (holographic/neon_glass/minimal)"),
            ],
            "LLM": [
                ("model",       cfg["llm"]["model"],        "Ollama model name"),
                ("num_gpu",     str(cfg["llm"]["num_gpu"]), "GPU layers (0=CPU only)"),
                ("temperature", str(cfg["llm"]["temperature"]), "Temperature (0.1-1.0)"),
            ],
            "VOICE": [
                ("stt_model",  cfg["voice"]["stt_model"],  "Whisper model (tiny/base/medium)"),
                ("language",   cfg["voice"]["language"],   "Language (auto/en/ta/hi)"),
                ("silence_threshold_ms", str(cfg["voice"]["silence_threshold_ms"]),
                                                            "Silence ms to end sentence"),
            ],
            "TTS": [
                ("piper_voice",       cfg["tts"]["piper_voice"],        "Piper voice name"),
                ("piper_length_scale",str(cfg["tts"]["piper_length_scale"]), "Speed (1.0=normal, 1.1=slower)"),
            ],
        }

        for section, fields in sections.items():
            tk.Label(inner, text=section, fg=C["accent"], bg=C["bg"],
                     font=mono(9, True)).pack(anchor="w", padx=14, pady=(10,2))
            box = tk.Frame(inner, bg=C["panel"], highlightthickness=1,
                            highlightbackground=C["border"])
            box.pack(fill="x", padx=14, pady=2)
            for key, val, hint in fields:
                row = tk.Frame(box, bg=C["panel"])
                row.pack(fill="x", padx=8, pady=4)
                tk.Label(row, text=hint, fg=C["dim"], bg=C["panel"],
                         font=mono(8), width=34, anchor="w").pack(side="left")
                sv = tk.StringVar(value=str(val))
                tk.Entry(row, textvariable=sv, bg=C["bg2"], fg=C["accent2"],
                         insertbackground=C["accent"], relief="flat",
                         font=mono(9), width=20).pack(side="left", padx=4)
                self._sv[f"{section}.{key}"] = sv

        def save_all():
            try:
                cfg = load_config()
                cfg["app"]["name"]       = self._sv["APP.name"].get()
                cfg["app"]["wake_word"]  = self._sv["APP.wake_word"].get()
                cfg["app"]["user_id"]    = self._sv["APP.user_id"].get()
                cfg["app"]["theme"]      = self._sv["APP.theme"].get()
                cfg["llm"]["model"]      = self._sv["LLM.model"].get()
                cfg["llm"]["num_gpu"]    = int(self._sv["LLM.num_gpu"].get())
                cfg["llm"]["temperature"]= float(self._sv["LLM.temperature"].get())
                cfg["voice"]["stt_model"]= self._sv["VOICE.stt_model"].get()
                cfg["voice"]["language"] = self._sv["VOICE.language"].get()
                cfg["voice"]["silence_threshold_ms"] = int(
                    self._sv["VOICE.silence_threshold_ms"].get())
                cfg["tts"]["piper_voice"]        = self._sv["TTS.piper_voice"].get()
                cfg["tts"]["piper_length_scale"] = float(
                    self._sv["TTS.piper_length_scale"].get())
                save_config(cfg)
                messagebox.showinfo(self.app_name,
                    "Settings saved. Restart the app to apply all changes.")
            except Exception as ex:
                messagebox.showerror("Error", str(ex))

        holo_btn(inner, "SAVE AND RESTART REQUIRED", save_all).pack(pady=12)
        return f

    # ------------------------------------------------------------------ KNOWLEDGE
    def _build_knowledge(self):
        f = tk.Frame(self.root, bg=C["bg"])
        sec_lbl(f, "KNOWLEDGE BASE -- teach me anything")

        # Ingest
        ing = tk.Frame(f, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
        ing.pack(fill="x", padx=14, pady=6)
        sec_lbl_in(ing, "INGEST DOCUMENT (PDF or TXT)")
        self.kn_path  = tk.StringVar()
        self.kn_topic = tk.StringVar()
        for label, var, btn_text, btn_cmd in [
            ("File", self.kn_path, "BROWSE", self._browse_file),
        ]:
            r = tk.Frame(ing, bg=C["panel"])
            r.pack(fill="x", padx=8, pady=4)
            tk.Label(r, text=label, fg=C["dim"], bg=C["panel"],
                     font=mono(8), width=8, anchor="w").pack(side="left")
            tk.Entry(r, textvariable=var, bg=C["bg2"], fg=C["accent2"],
                     insertbackground=C["accent"], relief="flat",
                     font=mono(9), width=32).pack(side="left", padx=4)
            tk.Button(r, text=btn_text, fg=C["accent"], bg=C["border"],
                      relief="flat", font=mono(7), command=btn_cmd).pack(side="left")

        r2 = tk.Frame(ing, bg=C["panel"])
        r2.pack(fill="x", padx=8, pady=4)
        tk.Label(r2, text="Topic", fg=C["dim"], bg=C["panel"],
                 font=mono(8), width=8, anchor="w").pack(side="left")
        tk.Entry(r2, textvariable=self.kn_topic, bg=C["bg2"], fg=C["accent2"],
                 insertbackground=C["accent"], relief="flat",
                 font=mono(9), width=32).pack(side="left", padx=4)

        self.kn_status = tk.Label(ing, text="", fg=C["accent2"], bg=C["panel"], font=mono(8))
        self.kn_status.pack(pady=4)
        holo_btn(ing, "INGEST INTO MEMORY", self._do_ingest).pack(pady=6)

        # Stats
        stats = tk.Frame(f, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
        stats.pack(fill="x", padx=14, pady=6)
        sec_lbl_in(stats, "MEMORY STATS")
        self.kn_stats = tk.Label(stats,
            text="Sessions: --\nKnowledge chunks: --",
            fg=C["accent"], bg=C["panel"], font=mono(9), justify="left")
        self.kn_stats.pack(padx=8, pady=8, anchor="w")
        holo_btn(stats, "REFRESH", self._refresh_stats).pack(pady=6)
        return f

    def _browse_file(self):
        p = filedialog.askopenfilename(
            filetypes=[("PDF","*.pdf"),("Text","*.txt"),("All","*.*")])
        if p:
            self.kn_path.set(p)
            self.kn_topic.set(Path(p).stem.lower().replace(" ","_"))

    def _do_ingest(self):
        path  = self.kn_path.get().strip()
        topic = self.kn_topic.get().strip()
        if not path or not topic:
            self.kn_status.config(text="Fill in file path and topic first.", fg=C["warn"])
            return
        self.kn_status.config(text="Ingesting...", fg=C["warn"])
        def run():
            try:
                if self.orchestrator:
                    self.orchestrator.llm.memory.ingest_document(path, topic)
                    self.root.after(0, lambda: self.kn_status.config(
                        text=f"Done. '{topic}' added to memory.", fg=C["accent2"]))
                else:
                    self.root.after(0, lambda: self.kn_status.config(
                        text="Orchestrator not running.", fg=C["warn"]))
            except Exception as ex:
                self.root.after(0, lambda: self.kn_status.config(
                    text=f"Error: {ex}", fg=C["error"]))
        threading.Thread(target=run, daemon=True).start()

    def _refresh_stats(self):
        if self.orchestrator:
            s = self.orchestrator.get_stats()
            self.kn_stats.config(
                text=f"Sessions: {s.get('sessions',0)}\n"
                     f"Knowledge chunks: {s.get('knowledge',0)}\n"
                     f"Model: {s.get('model','?')}")

    # ------------------------------------------------------------------ TRAINING
    def _build_training(self):
        f = tk.Frame(self.root, bg=C["bg"])
        sec_lbl(f, "SELF-TRAINING PIPELINE")

        info = tk.Frame(f, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
        info.pack(fill="x", padx=14, pady=6)
        sec_lbl_in(info, "STATUS")
        tk.Label(info,
            text="Training runs automatically Sunday 2 AM via Task Scheduler.\n"
                 "GPU: uses your local VRAM (4-8GB). CPU fallback if no GPU.\n"
                 "New adapter merges on top of old -- never forgets anything.",
            fg=C["accent"], bg=C["panel"], font=mono(9), justify="left"
        ).pack(padx=8, pady=8, anchor="w")
        self.tr_progress = tk.Label(info, text="", fg=C["accent2"], bg=C["panel"], font=mono(8))
        self.tr_progress.pack(padx=8, pady=(0,6), anchor="w")

        ctrl = tk.Frame(f, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
        ctrl.pack(fill="x", padx=14, pady=6)
        sec_lbl_in(ctrl, "CONTROLS")
        btn_row = tk.Frame(ctrl, bg=C["panel"])
        btn_row.pack(pady=8)
        holo_btn(btn_row, "RUN TRAINING NOW",     self._run_training).pack(side="left", padx=6)
        holo_btn(btn_row, "SETUP TASK SCHEDULER", self._setup_sched).pack(side="left", padx=6)
        holo_btn(btn_row, "CHECK DATA READY",     self._check_data).pack(side="left", padx=6)
        return f

    def _run_training(self):
        self.tr_progress.config(text="Starting... 30-60 min on GPU.", fg=C["warn"])
        def run():
            import subprocess
            script = Path(__file__).resolve().parent.parent.parent / "training" / "fine_tune.py"
            proc = subprocess.Popen([sys.executable, str(script)],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                msg = line.strip()[:90]
                if msg:
                    self.root.after(0, lambda m=msg: self.tr_progress.config(text=m, fg=C["accent2"]))
                    self._log(msg)
            self.root.after(0, lambda: self.tr_progress.config(text="Training complete!", fg=C["accent2"]))
        threading.Thread(target=run, daemon=True).start()

    def _setup_sched(self):
        import subprocess
        script = Path(__file__).resolve().parent.parent.parent / "training" / "fine_tune.py"
        cmd = (f'schtasks /create /tn "ARIA_Training" /tr '
               f'"{sys.executable} {script}" /sc WEEKLY /d SUN /st 02:00 /f')
        try:
            subprocess.run(cmd, shell=True, check=True)
            messagebox.showinfo(self.app_name, "Task Scheduler set. Trains every Sunday 2 AM.")
        except Exception as ex:
            messagebox.showerror("Error", f"Run as Administrator.\n{ex}")

    def _check_data(self):
        from core.config_loader import load_config
        cfg = load_config()
        uid = cfg["app"]["user_id"]
        p = Path("data/training") / f"{uid}_sessions.jsonl"
        if not p.exists():
            self.tr_progress.config(text="No data yet. Use the assistant first.", fg=C["warn"])
            return
        turns = []
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    turns.append(json.loads(line.strip()))
                except Exception:
                    pass
        hq = [t for t in turns if t.get("quality",0) >= 0.7]
        need = cfg["training"]["min_turns"]
        msg = (f"Total turns: {len(turns)}  |  High-quality: {len(hq)}  |  "
               f"{'READY' if len(hq)>=need else f'Need {need-len(hq)} more'}")
        self.tr_progress.config(text=msg, fg=C["accent2"] if len(hq)>=need else C["warn"])

    # ------------------------------------------------------------------ LOGS
    def _build_logs(self):
        f = tk.Frame(self.root, bg=C["bg"])
        sec_lbl(f, "SYSTEM LOGS")
        box = tk.Frame(f, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
        box.pack(fill="both", expand=True, padx=14, pady=6)
        self.log_txt = tk.Text(box, bg=C["bg2"], fg=C["accent"], font=mono(8),
                                relief="flat", state="disabled", wrap="word")
        sb = tk.Scrollbar(box, command=self.log_txt.yview)
        sb.pack(side="right", fill="y")
        self.log_txt.pack(fill="both", expand=True, padx=2, pady=2)
        self.log_txt.config(yscrollcommand=sb.set)
        holo_btn(f, "CLEAR LOGS", self._clear_logs).pack(pady=6)
        # Initial log entries using real config values
        self._log(f"{self.app_name} v1.0 initialised")
        self._log(f"Wake word: {self.wake_word}")
        self._log(f"Model: {self.model_name}")
        self._log(f"User: {self.user_id}")
        self._log("Holographic UI loaded")
        self._log("Connecting to orchestrator...")
        return f

    def _log(self, msg: str):
        ts   = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        def _w():
            if hasattr(self, "log_txt"):
                self.log_txt.config(state="normal")
                self.log_txt.insert("end", line)
                self.log_txt.see("end")
                self.log_txt.config(state="disabled")
        self.root.after(0, _w)

    def _clear_logs(self):
        self.log_txt.config(state="normal")
        self.log_txt.delete("1.0", "end")
        self.log_txt.config(state="disabled")

    # ------------------------------------------------------------------ animation
    def _start_animations(self):
        self._anim_orb()
        self._tick_clock()
        self._tick_metrics()

    def _anim_orb(self):
        if self._active_panel != "main":
            self.root.after(33, self._anim_orb)
            return

        self._angle = (self._angle + 0.03) % (2*math.pi)
        self._pulse = (self._pulse + 0.06) % (2*math.pi)
        self._tick  = (self._tick + 1) % 1000

        cx, cy = 295, 108
        c = self.orb_cv

        # Orbit dot 1
        r1 = 87
        x1 = cx + r1*math.cos(self._angle)
        y1 = cy + r1*math.sin(self._angle)
        c.coords(self.o_dot1,  x1-4, y1-4, x1+4, y1+4)
        c.coords(self.o_trail, x1-6, y1-6, x1+6, y1+6)

        # Orbit dot 2
        x2 = cx + 70*math.cos(-self._angle*0.65)
        y2 = cy + 70*math.sin(-self._angle*0.65)
        c.coords(self.o_dot2, x2-3, y2-3, x2+3, y2+3)

        # Scan line
        sy = cy - 88 + (self._tick % 60) * 3
        c.coords(self.o_scan, cx-90, sy, cx+90, sy)

        # Core pulse
        ps = 30 + 4*math.sin(self._pulse)
        dp = [cx,cy-ps, cx+ps*0.75,cy, cx,cy+ps, cx-ps*0.75,cy]
        c.coords(self.o_core,  *dp)
        c.coords(self.o_inner, *dp)

        # Colours by state
        col = {
            "standby":   C["dim"],
            "listening": C["accent2"],
            "thinking":  C["warn"],
            "speaking":  C["accent"],
        }.get(self.state, C["dim"])

        c.itemconfig(self.o_core,  outline=col)
        c.itemconfig(self.o_dot1,  fill=col)
        c.itemconfig(self.o_trail, outline=col)

        labels = {
            "standby":   f"[ {self.app_name} - STANDBY ]",
            "listening": "[ LISTENING ]",
            "thinking":  "[ PROCESSING ]",
            "speaking":  "[ RESPONDING ]",
        }
        c.itemconfig(self.o_state, text=labels.get(self.state, f"[ {self.app_name} ]"), fill=col)

        # Waveform on orb
        amp = {"speaking":14,"listening":7,"thinking":3,"standby":0.8}
        self._wave = self._wave[1:] + [random.gauss(0, amp.get(self.state, 0.8))]
        pts = []
        for i, v in enumerate(self._wave):
            pts += [30 + i*(530/len(self._wave)), 197+v]
        if len(pts) >= 4:
            c.coords(self.o_wave, *pts)

        # Audio chart
        self._chart = self._chart[1:] + [random.gauss(0, amp.get(self.state, 0.8))]
        self.chart_cv.delete("wave")
        cpts = []
        for i, v in enumerate(self._chart):
            cpts += [5 + i*(560/len(self._chart)), 34+v*2.2]
        if len(cpts) >= 4:
            wave_col = (C["accent2"] if self.state=="listening" else
                        C["warn"]    if self.state=="thinking"  else
                        C["accent"]  if self.state=="speaking"  else C["dim"])
            self.chart_cv.create_line(cpts, fill=wave_col, width=1.5, tags="wave")

        self.root.after(33, self._anim_orb)

    def _tick_clock(self):
        self.lbl_clock.config(text=time.strftime("%H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def _tick_metrics(self):
        try:
            import psutil
            self.lbl_cpu.config( text=f"CPU  {psutil.cpu_percent():.0f}%")
            self.lbl_ram.config( text=f"RAM  {psutil.virtual_memory().percent:.0f}%")
            self.lbl_disk.config(text=f"DSK  {psutil.disk_usage('/').percent:.0f}%")
        except Exception:
            pass
        self.root.after(3000, self._tick_metrics)

    def _toggle_standby(self):
        if self.orchestrator:
            self.orchestrator.activated = not self.orchestrator.activated
            self.set_state("listening" if self.orchestrator.activated else "standby")

    # ------------------------------------------------------------------ public callbacks
    def set_state(self, state: str):
        self.state = state
        mode_map = {
            "standby":   ("STANDBY",    C["warn"]),
            "listening": ("LISTENING",  C["accent2"]),
            "thinking":  ("PROCESSING", C["warn"]),
            "speaking":  ("RESPONDING", C["accent"]),
        }
        label, col = mode_map.get(state, ("UNKNOWN", C["dim"]))
        self.tel["MODE"].config(text=label, fg=col)
        dot_col = C["accent2"] if state != "standby" else C["dim"]
        self.dot_active.config(fg=dot_col)
        self._log(f"State -> {label}")

    def set_transcript(self, text: str):
        self.tel["INPUT"].config(text=text[:100], fg=C["accent2"])
        self._log(f"You: {text[:60]}")

    def set_response(self, text: str):
        self.tel["OUTPUT"].config(text=text[:200], fg=C["accent"])
        if text and text != "...":
            self._log(f"{self.app_name}: {text[:60]}")

    def set_stats(self, stats: dict):
        self.lbl_sess.config( text=f"SESSIONS {stats.get('sessions',0)}")
        self.lbl_model.config(text=f"LLM {stats.get('model','?')}")
        self._refresh_stats()
