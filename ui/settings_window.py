"""
ASTRA In-App Settings Window
Allows changing AI name, theme, and features without web portal.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Theme colors
C = {
    "bg": "#0f172a",
    "panel": "#1e293b",
    "accent": "#22d3ee",
    "text": "#e2e8f0",
    "dim": "#64748b",
}

THEMES = {
    "holographic": {"name": "Holographic", "desc": "Sci-Fi Iron Man style"},
    "neon_glass": {"name": "Neon Glass", "desc": "Modern purple gradient"},
    "minimal": {"name": "Minimal Dark", "desc": "Clean Apple style"},
}

VOICE_GENDERS = {
    "female": "👩 Female",
    "male": "👨 Male",
}

VOICE_TONES = {
    "soft": "Soft - Gentle & calm",
    "medium": "Medium - Natural & balanced",
    "strong": "Strong - Clear & assertive",
}

# Piper voice mapping
PIPER_VOICES = {
    "female": {
        "soft": "en_US-amy-low",
        "medium": "en_US-amy-medium", 
        "strong": "en_US-ljspeech-high",
    },
    "male": {
        "soft": "en_US-ryan-low",
        "medium": "en_US-ryan-medium",
        "strong": "en_US-ryan-high",
    }
}

TONE_SPEEDS = {
    "soft": 1.1,
    "medium": 1.0,
    "strong": 0.9,
}


class SettingsWindow:
    """In-app settings window for quick configuration changes."""
    
    def __init__(self, parent, on_save=None):
        self.parent = parent
        self.on_save = on_save
        
        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title("ASTRA Settings")
        self.window.geometry("500x720")
        self.window.configure(bg=C["bg"])
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        
        # Center on parent
        self.window.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 720) // 2
        self.window.geometry(f"+{x}+{y}")
        
        # Load current config
        self._load_config()
        
        # Build UI
        self._build_ui()
    
    def _load_config(self):
        """Load current configuration."""
        from core.config_loader import load_config
        self.cfg = load_config()
        
        # Also load user profile
        user_file = ROOT / "data" / "user_profile.json"
        if user_file.exists():
            self.user_data = json.loads(user_file.read_text())
        else:
            self.user_data = {}
    
    def _build_ui(self):
        # Header
        header = tk.Frame(self.window, bg=C["panel"], height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="⚙ Settings", font=("Arial", 14, "bold"),
                 fg=C["accent"], bg=C["panel"]).pack(side="left", padx=20, pady=12)
        
        # Content
        content = tk.Frame(self.window, bg=C["bg"])
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # === AI Name ===
        self._section_header(content, "AI Identity")
        
        name_frame = tk.Frame(content, bg=C["panel"], padx=15, pady=15)
        name_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(name_frame, text="AI Name (also your wake word)",
                 font=("Arial", 10), fg=C["dim"], bg=C["panel"]).pack(anchor="w")
        
        self.ai_name_var = tk.StringVar(value=self.cfg["app"].get("ai_name", ""))
        self.ai_name_entry = tk.Entry(name_frame, textvariable=self.ai_name_var,
                                       font=("Arial", 14, "bold"), bg="#334155",
                                       fg=C["accent"], relief="flat", insertbackground=C["accent"])
        self.ai_name_entry.pack(fill="x", pady=(5, 0), ipady=8)
        
        tk.Label(name_frame, text=f"You'll say: '[AI Name], open Chrome'",
                 font=("Arial", 9), fg=C["dim"], bg=C["panel"]).pack(anchor="w", pady=(5, 0))
        
        # User name
        tk.Label(name_frame, text="Your Name",
                 font=("Arial", 10), fg=C["dim"], bg=C["panel"]).pack(anchor="w", pady=(15, 0))
        
        self.user_name_var = tk.StringVar(value=self.cfg["app"].get("user_name", "User"))
        tk.Entry(name_frame, textvariable=self.user_name_var,
                 font=("Arial", 12), bg="#334155", fg=C["text"],
                 relief="flat", insertbackground=C["text"]).pack(fill="x", pady=(5, 0), ipady=6)
        
        # === Theme ===
        self._section_header(content, "Theme")
        
        theme_frame = tk.Frame(content, bg=C["panel"], padx=15, pady=15)
        theme_frame.pack(fill="x", pady=(0, 15))
        
        self.theme_var = tk.StringVar(value=self.cfg["app"].get("theme", "holographic"))
        
        for theme_id, theme in THEMES.items():
            rb_frame = tk.Frame(theme_frame, bg=C["panel"])
            rb_frame.pack(fill="x", pady=3)
            
            rb = tk.Radiobutton(rb_frame, text=f"{theme['name']} - {theme['desc']}",
                                variable=self.theme_var, value=theme_id,
                                font=("Arial", 10), fg=C["text"], bg=C["panel"],
                                selectcolor=C["bg"], activebackground=C["panel"],
                                activeforeground=C["accent"])
            rb.pack(anchor="w")
        
        # === AI Voice ===
        self._section_header(content, "AI Voice")
        
        ai_voice_frame = tk.Frame(content, bg=C["panel"], padx=15, pady=15)
        ai_voice_frame.pack(fill="x", pady=(0, 15))
        
        # Voice Gender
        gender_row = tk.Frame(ai_voice_frame, bg=C["panel"])
        gender_row.pack(fill="x", pady=(0, 8))
        
        tk.Label(gender_row, text="Voice Type:", font=("Arial", 10),
                 fg=C["dim"], bg=C["panel"], width=12, anchor="w").pack(side="left")
        
        self.voice_gender_var = tk.StringVar(value=self.cfg["tts"].get("voice_gender", "female"))
        for gender_id, gender_text in VOICE_GENDERS.items():
            rb = tk.Radiobutton(gender_row, text=gender_text,
                                variable=self.voice_gender_var, value=gender_id,
                                font=("Arial", 10), fg=C["text"], bg=C["panel"],
                                selectcolor=C["bg"], activebackground=C["panel"])
            rb.pack(side="left", padx=5)
        
        # Voice Tone
        tone_row = tk.Frame(ai_voice_frame, bg=C["panel"])
        tone_row.pack(fill="x")
        
        tk.Label(tone_row, text="Voice Style:", font=("Arial", 10),
                 fg=C["dim"], bg=C["panel"], width=12, anchor="w").pack(side="left")
        
        self.voice_tone_var = tk.StringVar(value=self.cfg["tts"].get("voice_tone", "medium"))
        for tone_id, tone_text in VOICE_TONES.items():
            rb = tk.Radiobutton(tone_row, text=tone_id.capitalize(),
                                variable=self.voice_tone_var, value=tone_id,
                                font=("Arial", 10), fg=C["text"], bg=C["panel"],
                                selectcolor=C["bg"], activebackground=C["panel"])
            rb.pack(side="left", padx=5)
        
        # === Voice Recognition ===
        self._section_header(content, "Voice Recognition")
        
        voice_frame = tk.Frame(content, bg=C["panel"], padx=15, pady=15)
        voice_frame.pack(fill="x", pady=(0, 15))
        
        self.voice_auth_var = tk.BooleanVar(value=self.cfg["voice"].get("voice_auth_enabled", False))
        tk.Checkbutton(voice_frame, text="Only respond to my voice",
                       variable=self.voice_auth_var, font=("Arial", 10),
                       fg=C["text"], bg=C["panel"], selectcolor=C["bg"],
                       activebackground=C["panel"]).pack(anchor="w")
        
        tk.Label(voice_frame, text="(Requires voice enrollment - record 3+ samples)",
                 font=("Arial", 9), fg=C["dim"], bg=C["panel"]).pack(anchor="w")
        
        enroll_btn = tk.Button(voice_frame, text="Enroll Voice Samples",
                               font=("Arial", 10), fg=C["accent"], bg="#334155",
                               relief="flat", padx=15, pady=5,
                               command=self._enroll_voice)
        enroll_btn.pack(anchor="w", pady=(10, 0))
        
        # === Buttons ===
        btn_frame = tk.Frame(self.window, bg=C["bg"])
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        tk.Button(btn_frame, text="Cancel", font=("Arial", 11),
                  fg=C["dim"], bg=C["panel"], relief="flat", padx=20, pady=8,
                  command=self.window.destroy).pack(side="left")
        
        tk.Button(btn_frame, text="Save & Restart", font=("Arial", 11, "bold"),
                  fg="white", bg="#0891b2", relief="flat", padx=20, pady=8,
                  command=self._save).pack(side="right")
        
        # Restart notice
        tk.Label(self.window, text="Note: Some changes require restart to take effect",
                 font=("Arial", 9), fg=C["dim"], bg=C["bg"]).pack(pady=(0, 10))
    
    def _section_header(self, parent, text):
        tk.Label(parent, text=text, font=("Arial", 11, "bold"),
                 fg=C["text"], bg=C["bg"]).pack(anchor="w", pady=(10, 5))
    
    def _enroll_voice(self):
        """Open voice enrollment dialog."""
        messagebox.showinfo("Voice Enrollment",
            "To enroll your voice:\n\n"
            "1. Run the setup wizard again\n"
            "2. Or record samples manually in data/voice_samples/\n\n"
            "Record 3-5 samples of 10-20 seconds each,\n"
            "speaking naturally.")
    
    def _save(self):
        """Save settings and trigger restart."""
        from core.config_generator import update_config
        
        ai_name = self.ai_name_var.get().strip() or "Astra"
        user_name = self.user_name_var.get().strip() or "User"
        voice_gender = self.voice_gender_var.get()
        voice_tone = self.voice_tone_var.get()
        
        # Get Piper voice from gender + tone
        piper_voice = PIPER_VOICES.get(voice_gender, {}).get(voice_tone, "en_US-amy-medium")
        voice_speed = TONE_SPEEDS.get(voice_tone, 1.0)
        
        # Use dynamic config updater - auto-generates personality
        update_config(
            ai_name=ai_name,
            user_name=user_name,
            theme=self.theme_var.get(),
            voice_auth_enabled=self.voice_auth_var.get(),
            voice_gender=voice_gender,
            voice_tone=voice_tone,
            piper_voice=piper_voice,
            piper_length_scale=voice_speed,
        )
        
        # Update user profile
        user_file = ROOT / "data" / "user_profile.json"
        if user_file.exists():
            user_data = json.loads(user_file.read_text())
        else:
            user_data = {}
        
        user_data["ai_name"] = ai_name
        user_data["user_name"] = user_name
        user_data["theme"] = self.theme_var.get()
        user_data["voice_gender"] = voice_gender
        user_data["voice_tone"] = voice_tone
        
        user_file.parent.mkdir(parents=True, exist_ok=True)
        user_file.write_text(json.dumps(user_data, indent=2))
        
        # Show message and close
        if messagebox.askyesno("Settings Saved",
            f"Settings saved successfully!\n\n"
            f"AI Name: {ai_name}\n"
            f"Wake Word: {ai_name.lower()}\n\n"
            f"Restart ASTRA now to apply changes?"):
            self.window.destroy()
            if self.on_save:
                self.on_save()
            # Trigger restart
            import sys
            import os
            os.execv(sys.executable, ['python'] + sys.argv)
        else:
            self.window.destroy()


def open_settings(parent, on_save=None):
    """Open settings window."""
    SettingsWindow(parent, on_save)
