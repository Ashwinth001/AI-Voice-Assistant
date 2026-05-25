"""
ARIA UI -- Theme 2: NEON GLASS
Deep purple/navy, pink-purple neon accents, glassmorphism panels
Clean modern AI assistant look
"""
import tkinter as tk
from tkinter import font as tkfont
import math, time, random

C = {
    "bg":       "#0a0a1a",
    "panel":    "#12122a",
    "border":   "#2d1b69",
    "accent":   "#c084fc",
    "accent2":  "#f472b6",
    "accent3":  "#38bdf8",
    "text":     "#e2d9f3",
    "dim":      "#4c3d7a",
    "success":  "#4ade80",
    "warn":     "#fbbf24",
}

class NeonGlassUI:
    def __init__(self, root: tk.Tk, orchestrator=None):
        self.root = root
        self.orchestrator = orchestrator
        self.state = "standby"
        self._tick = 0
        self._wave = [0] * 100
        self._setup()
        self._build()
        self._animate()
        self._clock()

    def _setup(self):
        self.root.title("ARIA")
        self.root.geometry("560x820")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)
        self.fn = tkfont.Font(family="Segoe UI", size=10)
        self.fn_lg = tkfont.Font(family="Segoe UI", size=20, weight="bold")
        self.fn_sm = tkfont.Font(family="Segoe UI", size=8)
        self.fn_mono = tkfont.Font(family="Consolas", size=9)

    def _build(self):
        # Top
        top = tk.Frame(self.root, bg=C["bg"])
        top.pack(fill="x", padx=16, pady=(14, 0))
        tk.Label(top, text="ARIA", fg=C["accent"], bg=C["bg"], font=self.fn_lg).pack(side="left")
        tk.Label(top, text="Adaptive Reasoning Intelligence Assistant",
                  fg=C["dim"], bg=C["bg"], font=self.fn_sm).pack(side="left", padx=10, pady=(8,0))
        self.lbl_time = tk.Label(top, text="00:00", fg=C["dim"], bg=C["bg"], font=self.fn_sm)
        self.lbl_time.pack(side="right")

        # Status pill
        pill_frame = tk.Frame(self.root, bg=C["bg"])
        pill_frame.pack(pady=8)
        self.pill = tk.Label(pill_frame, text="   STANDBY  ", fg=C["dim"],
                              bg=C["panel"], font=self.fn_sm, relief="flat",
                              padx=8, pady=4)
        self.pill.pack()

        # Main orb canvas
        self.canvas = tk.Canvas(self.root, width=520, height=200,
                                 bg=C["bg"], highlightthickness=0)
        self.canvas.pack()
        self._draw_orb()

        # Transcript card
        card1 = tk.Frame(self.root, bg=C["panel"],
                          highlightthickness=1, highlightbackground=C["border"])
        card1.pack(fill="x", padx=16, pady=4)
        tk.Label(card1, text="YOU SAID", fg=C["dim"], bg=C["panel"],
                  font=self.fn_sm).pack(anchor="w", padx=10, pady=(8, 2))
        self.lbl_input = tk.Label(card1, text="Say 'aria' to wake me up",
                                   fg=C["text"], bg=C["panel"], font=self.fn,
                                   wraplength=480, justify="left", anchor="w")
        self.lbl_input.pack(fill="x", padx=10, pady=(0, 10))

        # Response card
        card2 = tk.Frame(self.root, bg=C["panel"],
                          highlightthickness=1, highlightbackground=C["border"])
        card2.pack(fill="x", padx=16, pady=4)
        tk.Label(card2, text="ARIA SAYS", fg=C["accent"], bg=C["panel"],
                  font=self.fn_sm).pack(anchor="w", padx=10, pady=(8, 2))
        self.lbl_output = tk.Label(card2, text="--", fg=C["text"], bg=C["panel"],
                                    font=self.fn, wraplength=480, justify="left", anchor="w")
        self.lbl_output.pack(fill="x", padx=10, pady=(0, 10))

        # Waveform
        self.wave_canvas = tk.Canvas(self.root, width=520, height=60,
                                      bg=C["panel"], highlightthickness=1,
                                      highlightbackground=C["border"])
        self.wave_canvas.pack(padx=16, pady=4)

        # System bars
        bars_frame = tk.Frame(self.root, bg=C["panel"],
                               highlightthickness=1, highlightbackground=C["border"])
        bars_frame.pack(fill="x", padx=16, pady=4)
        tk.Label(bars_frame, text="SYSTEMS", fg=C["dim"], bg=C["panel"],
                  font=self.fn_sm).pack(anchor="w", padx=10, pady=(8, 4))

        self.bars = {}
        for name, color in [("Voice STT", C["accent3"]),
                              ("LLM Core", C["accent"]),
                              ("Voice TTS", C["accent2"]),
                              ("Memory", C["success"])]:
            row = tk.Frame(bars_frame, bg=C["panel"])
            row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=name, fg=C["dim"], bg=C["panel"],
                      font=self.fn_sm, width=12, anchor="w").pack(side="left")
            bg = tk.Frame(row, bg=C["dim"], height=4, width=280)
            bg.pack(side="left", padx=6)
            bg.pack_propagate(False)
            bar = tk.Frame(bg, bg=color, height=4, width=280)
            bar.pack(fill="both")
            self.bars[name] = bar

        # Bottom info
        bot = tk.Frame(self.root, bg=C["bg"])
        bot.pack(fill="x", padx=16, pady=(4, 12))
        self.lbl_model = tk.Label(bot, text="phi3.5-mini * local",
                                   fg=C["dim"], bg=C["bg"], font=self.fn_sm)
        self.lbl_model.pack(side="left")
        self.lbl_sessions = tk.Label(bot, text="0 memories",
                                      fg=C["dim"], bg=C["bg"], font=self.fn_sm)
        self.lbl_sessions.pack(side="right")

    def _draw_orb(self):
        cx, cy = 260, 100
        # Glow rings
        for r, alpha in [(80, "#1a0a2e"), (65, "#220d3a"), (50, "#2d1060")]:
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=alpha, outline="")
        # Main orb
        self.orb_main = self.canvas.create_oval(cx-42, cy-42, cx+42, cy+42,
                                                  outline=C["accent"], width=2, fill=C["panel"])
        # Inner ring
        self.canvas.create_oval(cx-30, cy-30, cx+30, cy+30,
                                  outline=C["dim"], width=1, dash=(3, 5))
        # Dots on outer ring
        self.orbit_dots = []
        for i in range(4):
            d = self.canvas.create_oval(0, 0, 7, 7, fill=C["accent2"], outline="")
            self.orbit_dots.append(d)
        # State text
        self.orb_text = self.canvas.create_text(cx, cy, text="STANDBY",
                                                  fill=C["dim"], font=self.fn_sm)

    def _animate(self):
        self._tick += 1
        cx, cy = 260, 100

        # Orbit dots
        for i, dot in enumerate(self.orbit_dots):
            angle = math.radians(self._tick * 1.5 + i * 90)
            r = 75
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle) * 0.4  # elliptical
            self.canvas.coords(dot, x-3, y-3, x+3, y+3)

        # Pulse orb
        pulse = 42 + 3 * math.sin(self._tick * 0.08)
        self.canvas.coords(self.orb_main, cx-pulse, cy-pulse, cx+pulse, cy+pulse)

        # Waveform
        self._wave = self._wave[1:] + [
            random.gauss(0, 14 if self.state == "speaking"
                         else 6 if self.state == "listening" else 0.5)
        ]
        self.wave_canvas.delete("all")
        pts = []
        for i, v in enumerate(self._wave):
            x = 10 + i * (500 / len(self._wave))
            y = 30 + v
            pts.extend([x, y])
        if len(pts) >= 4:
            col = C["accent2"] if self.state == "speaking" else C["accent3"]
            self.wave_canvas.create_line(pts, fill=col, width=1.5, smooth=True)

        self.root.after(25, self._animate)

    def _clock(self):
        self.lbl_time.config(text=time.strftime("%H:%M"))
        self.root.after(1000, self._clock)

    def set_state(self, state: str):
        self.state = state
        texts = {"standby": "STANDBY", "listening": "LISTENING",
                 "thinking": "THINKING", "speaking": "SPEAKING"}
        colors = {"standby": C["dim"], "listening": C["success"],
                  "thinking": C["warn"], "speaking": C["accent"]}
        pill_colors = {"standby": C["dim"], "listening": C["success"],
                       "thinking": C["warn"], "speaking": C["accent"]}
        t = texts.get(state, state.upper())
        c = colors.get(state, C["dim"])
        self.canvas.itemconfig(self.orb_text, text=t, fill=c)
        self.canvas.itemconfig(self.orb_main, outline=c)
        self.pill.config(text=f"   {t}  ", fg=pill_colors.get(state, C["dim"]))

    def set_transcript(self, text: str):
        self.lbl_input.config(text=text[:120])

    def set_response(self, text: str):
        self.lbl_output.config(text=text[:300])

    def set_stats(self, stats: dict):
        self.lbl_model.config(text=f"{stats.get('model', '')} * local")
        self.lbl_sessions.config(text=f"{stats.get('sessions', 0)} memories")
