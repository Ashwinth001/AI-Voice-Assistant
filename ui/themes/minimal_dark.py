"""
ARIA UI -- Theme 3: MINIMAL DARK
Clean, Apple-inspired dark UI. Large text, breathing animation, simple status.
Most readable and professional.
"""
import tkinter as tk
from tkinter import font as tkfont
import math, time, random

C = {
    "bg":      "#111111",
    "panel":   "#1c1c1e",
    "border":  "#2c2c2e",
    "accent":  "#0a84ff",
    "green":   "#30d158",
    "yellow":  "#ffd60a",
    "red":     "#ff453a",
    "text":    "#ffffff",
    "dim":     "#8e8e93",
    "dim2":    "#3a3a3c",
}

class MinimalDarkUI:
    def __init__(self, root: tk.Tk, orchestrator=None):
        self.root = root
        self.orchestrator = orchestrator
        self.state = "standby"
        self._tick = 0
        self._wave = [0] * 120
        self._setup()
        self._build()
        self._animate()
        self._clock()

    def _setup(self):
        self.root.title("ARIA")
        self.root.geometry("520x760")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)
        self.fn_xl = tkfont.Font(family="SF Pro Display", size=36, weight="bold")
        self.fn_lg = tkfont.Font(family="Helvetica Neue", size=18)
        self.fn = tkfont.Font(family="Helvetica Neue", size=12)
        self.fn_sm = tkfont.Font(family="Helvetica Neue", size=10)
        self.fn_xs = tkfont.Font(family="Helvetica Neue", size=9)

    def _build(self):
        # Header
        hdr = tk.Frame(self.root, bg=C["bg"])
        hdr.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(hdr, text="ARIA", fg=C["text"], bg=C["bg"],
                  font=self.fn_xl).pack(side="left")
        right = tk.Frame(hdr, bg=C["bg"])
        right.pack(side="right")
        self.lbl_state_badge = tk.Label(right, text="Standby",
                                         fg=C["dim"], bg=C["dim2"],
                                         font=self.fn_xs, padx=8, pady=3)
        self.lbl_state_badge.pack()
        self.lbl_time = tk.Label(right, text="00:00:00",
                                  fg=C["dim"], bg=C["bg"], font=self.fn_xs)
        self.lbl_time.pack(pady=(4, 0))

        # Big breathing circle
        self.canvas = tk.Canvas(self.root, width=480, height=200,
                                 bg=C["bg"], highlightthickness=0)
        self.canvas.pack(pady=8)
        cx, cy = 240, 100
        # Background rings
        for r in [90, 75, 60]:
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                     outline=C["dim2"], width=1)
        self.orb = self.canvas.create_oval(cx-40, cy-40, cx+40, cy+40,
                                            fill=C["accent"], outline="", stipple="")
        self.orb_glow = self.canvas.create_oval(cx-48, cy-48, cx+48, cy+48,
                                                  outline=C["accent"], width=1)

        # Status text
        self.status_text = self.canvas.create_text(cx, cy+68, text="Standby",
                                                    fill=C["dim"], font=self.fn)

        # Divider
        div = tk.Frame(self.root, bg=C["border"], height=1)
        div.pack(fill="x", padx=24, pady=4)

        # Waveform
        self.wave_cv = tk.Canvas(self.root, width=472, height=50,
                                  bg=C["panel"], highlightthickness=0)
        self.wave_cv.pack(padx=24, pady=4)

        # You said
        self._section("YOU SAID")
        self.lbl_input = tk.Label(self.root, text='Say "aria" to start',
                                   fg=C["dim"], bg=C["bg"], font=self.fn,
                                   wraplength=460, justify="left", anchor="w")
        self.lbl_input.pack(fill="x", padx=24)

        div2 = tk.Frame(self.root, bg=C["border"], height=1)
        div2.pack(fill="x", padx=24, pady=8)

        # ARIA says
        self._section("ARIA SAYS")
        self.lbl_output = tk.Label(self.root, text="--",
                                    fg=C["text"], bg=C["bg"], font=self.fn,
                                    wraplength=460, justify="left", anchor="w")
        self.lbl_output.pack(fill="x", padx=24)

        div3 = tk.Frame(self.root, bg=C["border"], height=1)
        div3.pack(fill="x", padx=24, pady=12)

        # Status row
        bot = tk.Frame(self.root, bg=C["bg"])
        bot.pack(fill="x", padx=24, pady=(0, 16))

        self.lbl_dot = tk.Label(bot, text="", fg=C["dim"], bg=C["bg"],
                                 font=self.fn_xs)
        self.lbl_dot.pack(side="left")
        self.lbl_model = tk.Label(bot, text="phi3.5-mini",
                                   fg=C["dim"], bg=C["bg"], font=self.fn_xs)
        self.lbl_model.pack(side="left", padx=4)
        self.lbl_mem = tk.Label(bot, text="0 memories",
                                 fg=C["dim"], bg=C["bg"], font=self.fn_xs)
        self.lbl_mem.pack(side="right")

    def _section(self, label):
        tk.Label(self.root, text=label, fg=C["dim"], bg=C["bg"],
                  font=self.fn_xs).pack(anchor="w", padx=24, pady=(4, 2))

    def _animate(self):
        self._tick += 1
        cx, cy = 240, 100
        pulse = 38 + 5 * math.sin(self._tick * 0.06)
        state_col = {"standby": C["dim2"], "listening": C["green"],
                     "thinking": C["yellow"], "speaking": C["accent"]}.get(self.state, C["dim2"])
        self.canvas.itemconfig(self.orb, fill=state_col)
        self.canvas.coords(self.orb, cx-pulse, cy-pulse, cx+pulse, cy+pulse)

        glow = pulse + 8
        self.canvas.coords(self.orb_glow, cx-glow, cy-glow, cx+glow, cy+glow)
        self.canvas.itemconfig(self.orb_glow, outline=state_col)

        # Waveform
        amp = {"speaking": 18, "listening": 8, "thinking": 3, "standby": 0.3}
        self._wave = self._wave[1:] + [random.gauss(0, amp.get(self.state, 0.3))]
        self.wave_cv.delete("all")
        pts = []
        for i, v in enumerate(self._wave):
            x = i * (472 / len(self._wave))
            y = 25 + v
            pts.extend([x, y])
        if len(pts) >= 4:
            self.wave_cv.create_line(pts, fill=state_col, width=1.5, smooth=True)

        self.root.after(30, self._animate)

    def _clock(self):
        self.lbl_time.config(text=time.strftime("%H:%M:%S"))
        self.root.after(1000, self._clock)

    def set_state(self, state: str):
        self.state = state
        labels = {"standby": "Standby", "listening": "Listening",
                  "thinking": "Thinking", "speaking": "Speaking"}
        colors = {"standby": C["dim"], "listening": C["green"],
                  "thinking": C["yellow"], "speaking": C["accent"]}
        t = labels.get(state, state)
        c = colors.get(state, C["dim"])
        self.canvas.itemconfig(self.status_text, text=t, fill=c)
        self.lbl_state_badge.config(text=t, fg=c)
        self.lbl_dot.config(fg=c)

    def set_transcript(self, text: str):
        self.lbl_input.config(text=text[:150], fg=C["text"])

    def set_response(self, text: str):
        self.lbl_output.config(text=text[:400])

    def set_stats(self, stats: dict):
        self.lbl_model.config(text=stats.get("model", ""))
        self.lbl_mem.config(text=f"{stats.get('sessions', 0)} memories")
