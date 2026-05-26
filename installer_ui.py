"""
ASTRA Setup Wizard - In-App Registration
Advanced Self-Training Reasoning Assistant
Runs during first installation. No web server needed.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys
import hashlib
import threading
import wave
import struct
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config" / "config.yaml"
USER_FILE = ROOT / "data" / "user_profile.json"
VOICE_DIR = ROOT / "data" / "voice_samples"

# App branding (FIXED - cannot be changed)
APP_NAME = "ASTRA"  # Advanced Self-Training Reasoning Assistant
APP_FULL_NAME = "Advanced Self-Training Reasoning Assistant"
APP_VERSION = "2.0.0"
CREATOR = "Ashwinth"

# Theme definitions
THEMES = {
    "holographic": {"name": "Holographic", "desc": "Sci-Fi Iron Man style", "bg": "#020d18", "accent": "#00c8ff"},
    "neon_glass": {"name": "Neon Glass", "desc": "Modern purple gradient", "bg": "#1a0a2e", "accent": "#a855f7"},
    "minimal": {"name": "Minimal Dark", "desc": "Clean Apple style", "bg": "#1c1c1e", "accent": "#ffffff"},
}

# Voice options - maps to Piper TTS voices
VOICE_GENDERS = {
    "female": {"name": "Female", "icon": "👩"},
    "male": {"name": "Male", "icon": "👨"},
}

VOICE_TONES = {
    "soft": {"name": "Soft", "desc": "Gentle & calm", "speed": 1.1},
    "medium": {"name": "Medium", "desc": "Natural & balanced", "speed": 1.0},
    "strong": {"name": "Strong", "desc": "Clear & assertive", "speed": 0.9},
}

# Piper voice mapping (gender -> tone -> voice model)
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

class SetupWizard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} - Setup Wizard")
        self.root.geometry("600x700")
        self.root.configure(bg="#0f172a")
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 600) // 2
        y = (self.root.winfo_screenheight() - 700) // 2
        self.root.geometry(f"+{x}+{y}")
        
        # User data
        self.user_data = {
            "user_name": "",
            "ai_name": "",  # User will choose their own AI name
            "theme": "holographic",
            "voice_gender": "female",  # female / male
            "voice_tone": "medium",    # soft / medium / strong
            "voice_samples": [],
            "created": datetime.now().isoformat(),
        }
        
        self.current_step = 0
        self.steps = [
            self._step_welcome,
            self._step_user_info,
            self._step_ai_config,
            self._step_voice_enroll,
            self._step_complete,
        ]
        
        self._build_ui()
        self._show_step(0)
    
    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#1e293b", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text=f"⬡ {APP_NAME}", font=("Arial", 18, "bold"),
                 fg="#22d3ee", bg="#1e293b").pack(side="left", padx=20, pady=15)
        
        tk.Label(header, text="Setup Wizard", font=("Arial", 12),
                 fg="#94a3b8", bg="#1e293b").pack(side="left", padx=10, pady=15)
        
        # Progress bar
        self.progress_frame = tk.Frame(self.root, bg="#0f172a")
        self.progress_frame.pack(fill="x", padx=40, pady=20)
        
        self.progress_dots = []
        for i in range(5):
            dot = tk.Label(self.progress_frame, text="●", font=("Arial", 14),
                          fg="#334155", bg="#0f172a")
            dot.pack(side="left", expand=True)
            self.progress_dots.append(dot)
        
        # Content area
        self.content = tk.Frame(self.root, bg="#0f172a")
        self.content.pack(fill="both", expand=True, padx=40)
        
        # Navigation buttons
        nav = tk.Frame(self.root, bg="#0f172a")
        nav.pack(fill="x", padx=40, pady=20)
        
        self.btn_back = tk.Button(nav, text="← Back", font=("Arial", 11),
                                   fg="#94a3b8", bg="#334155", relief="flat",
                                   padx=20, pady=8, command=self._prev_step)
        self.btn_back.pack(side="left")
        
        self.btn_next = tk.Button(nav, text="Next →", font=("Arial", 11, "bold"),
                                   fg="white", bg="#0891b2", relief="flat",
                                   padx=20, pady=8, command=self._next_step)
        self.btn_next.pack(side="right")
    
    def _show_step(self, step_num):
        self.current_step = step_num
        
        # Update progress dots
        for i, dot in enumerate(self.progress_dots):
            if i < step_num:
                dot.config(fg="#22d3ee")
            elif i == step_num:
                dot.config(fg="#0891b2")
            else:
                dot.config(fg="#334155")
        
        # Update buttons
        self.btn_back.config(state="normal" if step_num > 0 else "disabled")
        self.btn_next.config(text="Finish" if step_num == 4 else "Next →")
        
        # Clear and show content
        for widget in self.content.winfo_children():
            widget.destroy()
        
        self.steps[step_num]()
    
    def _prev_step(self):
        if self.current_step > 0:
            self._show_step(self.current_step - 1)
    
    def _next_step(self):
        if self.current_step < 4:
            self._show_step(self.current_step + 1)
        else:
            self._finish()
    
    # ====================== STEP 1: Welcome ======================
    def _step_welcome(self):
        tk.Label(self.content, text=f"Welcome to {APP_NAME}",
                 font=("Arial", 24, "bold"), fg="white", bg="#0f172a").pack(pady=30)
        
        tk.Label(self.content, text="Your Personal AI Assistant",
                 font=("Arial", 14), fg="#94a3b8", bg="#0f172a").pack()
        
        # Logo placeholder
        logo_frame = tk.Frame(self.content, bg="#1e293b", width=150, height=150)
        logo_frame.pack(pady=40)
        logo_frame.pack_propagate(False)
        tk.Label(logo_frame, text="⬡", font=("Arial", 60), fg="#22d3ee", bg="#1e293b").place(relx=0.5, rely=0.5, anchor="center")
        
        info_text = f"""
{APP_NAME} is an intelligent voice assistant that:

• Controls your PC with voice commands
• Learns and remembers information
• Works offline with basic commands
• Improves through your feedback

Let's set up your personal AI in just a few steps.
"""
        tk.Label(self.content, text=info_text, font=("Arial", 11),
                 fg="#cbd5e1", bg="#0f172a", justify="left").pack(pady=20)
    
    # ====================== STEP 2: User Info ======================
    def _step_user_info(self):
        tk.Label(self.content, text="Tell us about yourself",
                 font=("Arial", 20, "bold"), fg="white", bg="#0f172a").pack(pady=20)
        
        tk.Label(self.content, text="This helps personalize your AI assistant.",
                 font=("Arial", 11), fg="#94a3b8", bg="#0f172a").pack(pady=(0, 30))
        
        # User name
        frame = tk.Frame(self.content, bg="#1e293b", padx=20, pady=20)
        frame.pack(fill="x", pady=10)
        
        tk.Label(frame, text="Your Name", font=("Arial", 10),
                 fg="#94a3b8", bg="#1e293b").pack(anchor="w")
        
        self.entry_username = tk.Entry(frame, font=("Arial", 14), bg="#334155",
                                        fg="white", relief="flat", insertbackground="white")
        self.entry_username.pack(fill="x", pady=(5, 0), ipady=8)
        self.entry_username.insert(0, self.user_data.get("user_name", ""))
        
        tk.Label(frame, text="Your AI will say: 'I am your personal assistant, [Your Name]'",
                 font=("Arial", 9), fg="#64748b", bg="#1e293b").pack(anchor="w", pady=(5, 0))
        
        # Bind to save on change
        self.entry_username.bind("<FocusOut>", lambda e: self._save_username())
    
    def _save_username(self):
        self.user_data["user_name"] = self.entry_username.get().strip()
    
    # ====================== STEP 3: AI Configuration ======================
    def _step_ai_config(self):
        tk.Label(self.content, text="Configure Your AI",
                 font=("Arial", 20, "bold"), fg="white", bg="#0f172a").pack(pady=(10, 15))
        
        # AI Name
        name_frame = tk.Frame(self.content, bg="#1e293b", padx=20, pady=12)
        name_frame.pack(fill="x", pady=5)
        
        tk.Label(name_frame, text="AI Name (also becomes your wake word)",
                 font=("Arial", 10), fg="#94a3b8", bg="#1e293b").pack(anchor="w")
        
        self.entry_ainame = tk.Entry(name_frame, font=("Arial", 14, "bold"),
                                      bg="#334155", fg="#22d3ee", relief="flat",
                                      insertbackground="#22d3ee")
        self.entry_ainame.pack(fill="x", pady=(5, 0), ipady=6)
        self.entry_ainame.insert(0, self.user_data.get("ai_name", ""))
        
        tk.Label(name_frame, text="Example: 'Nova, open Chrome' or 'Alex, search Google'",
                 font=("Arial", 9), fg="#64748b", bg="#1e293b").pack(anchor="w", pady=(3, 0))
        
        # Voice Selection Section
        tk.Label(self.content, text="AI Voice", font=("Arial", 12, "bold"),
                 fg="white", bg="#0f172a").pack(anchor="w", pady=(15, 5))
        
        voice_frame = tk.Frame(self.content, bg="#1e293b", padx=20, pady=12)
        voice_frame.pack(fill="x", pady=5)
        
        # Gender selection (row 1)
        gender_row = tk.Frame(voice_frame, bg="#1e293b")
        gender_row.pack(fill="x", pady=(0, 10))
        
        tk.Label(gender_row, text="Voice Type:", font=("Arial", 10),
                 fg="#94a3b8", bg="#1e293b", width=12, anchor="w").pack(side="left")
        
        self.voice_gender_var = tk.StringVar(value=self.user_data.get("voice_gender", "female"))
        
        for gender_id, gender in VOICE_GENDERS.items():
            rb = tk.Radiobutton(gender_row, text=f"{gender['icon']} {gender['name']}",
                                variable=self.voice_gender_var, value=gender_id,
                                font=("Arial", 11), fg="white", bg="#1e293b",
                                activebackground="#1e293b", selectcolor="#0891b2",
                                padx=15)
            rb.pack(side="left")
        
        # Tone selection (row 2)
        tone_row = tk.Frame(voice_frame, bg="#1e293b")
        tone_row.pack(fill="x")
        
        tk.Label(tone_row, text="Voice Style:", font=("Arial", 10),
                 fg="#94a3b8", bg="#1e293b", width=12, anchor="w").pack(side="left")
        
        self.voice_tone_var = tk.StringVar(value=self.user_data.get("voice_tone", "medium"))
        
        for tone_id, tone in VOICE_TONES.items():
            rb = tk.Radiobutton(tone_row, text=f"{tone['name']}",
                                variable=self.voice_tone_var, value=tone_id,
                                font=("Arial", 11), fg="white", bg="#1e293b",
                                activebackground="#1e293b", selectcolor="#0891b2",
                                padx=10)
            rb.pack(side="left")
        
        # Theme selection
        tk.Label(self.content, text="UI Theme", font=("Arial", 12, "bold"),
                 fg="white", bg="#0f172a").pack(anchor="w", pady=(15, 5))
        
        self.theme_var = tk.StringVar(value=self.user_data.get("theme", "holographic"))
        
        theme_container = tk.Frame(self.content, bg="#0f172a")
        theme_container.pack(fill="x")
        
        for theme_id, theme in THEMES.items():
            frame = tk.Frame(theme_container, bg="#1e293b", padx=12, pady=10)
            frame.pack(fill="x", pady=3)
            
            rb = tk.Radiobutton(frame, text="", variable=self.theme_var,
                                value=theme_id, bg="#1e293b", activebackground="#1e293b",
                                selectcolor="#0891b2")
            rb.pack(side="left")
            
            # Color preview
            color_box = tk.Frame(frame, bg=theme["accent"], width=16, height=16)
            color_box.pack(side="left", padx=(0, 8))
            
            tk.Label(frame, text=theme["name"], font=("Arial", 10, "bold"),
                     fg="white", bg="#1e293b").pack(side="left")
            
            tk.Label(frame, text=f" - {theme['desc']}", font=("Arial", 9),
                     fg="#64748b", bg="#1e293b").pack(side="left")
        
        # Bind to save
        self.entry_ainame.bind("<FocusOut>", lambda e: self._save_aiconfig())
        self.theme_var.trace("w", lambda *args: self._save_aiconfig())
        self.voice_gender_var.trace("w", lambda *args: self._save_aiconfig())
        self.voice_tone_var.trace("w", lambda *args: self._save_aiconfig())
    
    def _save_aiconfig(self):
        self.user_data["ai_name"] = self.entry_ainame.get().strip()
        self.user_data["theme"] = self.theme_var.get()
        self.user_data["voice_gender"] = self.voice_gender_var.get()
        self.user_data["voice_tone"] = self.voice_tone_var.get()
    
    # ====================== STEP 4: Voice Enrollment ======================
    def _step_voice_enroll(self):
        tk.Label(self.content, text="Voice Recognition Setup",
                 font=("Arial", 20, "bold"), fg="white", bg="#0f172a").pack(pady=20)
        
        tk.Label(self.content, 
                 text="Record your voice so the AI only responds to YOU.\n"
                      "This prevents others from controlling your PC.",
                 font=("Arial", 11), fg="#94a3b8", bg="#0f172a", justify="center").pack()
        
        # Recording status
        self.voice_status = tk.Label(self.content, text="Record 3-5 samples (10-20 seconds each)",
                                      font=("Arial", 10), fg="#64748b", bg="#0f172a")
        self.voice_status.pack(pady=20)
        
        # Record button
        self.btn_record = tk.Button(self.content, text="🎤 Start Recording",
                                     font=("Arial", 12, "bold"), fg="white",
                                     bg="#dc2626", relief="flat", padx=30, pady=15,
                                     command=self._toggle_recording)
        self.btn_record.pack(pady=10)
        
        # Sample list
        self.sample_frame = tk.Frame(self.content, bg="#0f172a")
        self.sample_frame.pack(fill="x", pady=20)
        
        self._update_sample_list()
        
        # Skip option
        tk.Label(self.content, 
                 text="(You can skip this and set up voice recognition later in Settings)",
                 font=("Arial", 9), fg="#475569", bg="#0f172a").pack(pady=10)
        
        self._recording = False
        self._audio_data = []
    
    def _toggle_recording(self):
        if not self._recording:
            self._start_recording()
        else:
            self._stop_recording()
    
    def _start_recording(self):
        self._recording = True
        self.btn_record.config(text="⏹ Stop Recording", bg="#22c55e")
        self.voice_status.config(text="Recording... Speak naturally for 10-20 seconds", fg="#22c55e")
        
        # Start recording in background
        def record():
            try:
                import pyaudio
                CHUNK = 1024
                FORMAT = pyaudio.paInt16
                CHANNELS = 1
                RATE = 16000
                
                p = pyaudio.PyAudio()
                stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                               input=True, frames_per_buffer=CHUNK)
                
                self._audio_data = []
                while self._recording:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    self._audio_data.append(data)
                
                stream.stop_stream()
                stream.close()
                p.terminate()
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Recording failed: {e}"))
        
        threading.Thread(target=record, daemon=True).start()
    
    def _stop_recording(self):
        self._recording = False
        self.btn_record.config(text="🎤 Start Recording", bg="#dc2626")
        
        if len(self._audio_data) > 10:  # At least ~0.5 seconds
            self._save_voice_sample()
        else:
            self.voice_status.config(text="Recording too short. Try again.", fg="#f59e0b")
    
    def _save_voice_sample(self):
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        
        sample_num = len(self.user_data["voice_samples"]) + 1
        filename = f"voice_sample_{sample_num}.wav"
        filepath = VOICE_DIR / filename
        
        # Save as WAV
        try:
            import wave
            wf = wave.open(str(filepath), 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b''.join(self._audio_data))
            wf.close()
            
            self.user_data["voice_samples"].append(str(filepath))
            self._update_sample_list()
            self.voice_status.config(
                text=f"Sample {sample_num} saved! Record more for better accuracy.",
                fg="#22d3ee"
            )
        except Exception as e:
            self.voice_status.config(text=f"Save failed: {e}", fg="#ef4444")
    
    def _update_sample_list(self):
        for widget in self.sample_frame.winfo_children():
            widget.destroy()
        
        for i, sample in enumerate(self.user_data["voice_samples"], 1):
            frame = tk.Frame(self.sample_frame, bg="#1e293b", padx=10, pady=5)
            frame.pack(fill="x", pady=2)
            tk.Label(frame, text=f"✓ Sample {i}", font=("Arial", 10),
                     fg="#22c55e", bg="#1e293b").pack(side="left")
    
    # ====================== STEP 5: Complete ======================
    def _step_complete(self):
        self._save_username()
        self._save_aiconfig()
        
        ai_name = self.user_data.get("ai_name") or "Astra"
        user_name = self.user_data.get("user_name", "User")
        voice_gender = self.user_data.get("voice_gender", "female")
        voice_tone = self.user_data.get("voice_tone", "medium")
        
        tk.Label(self.content, text="Setup Complete! 🎉",
                 font=("Arial", 24, "bold"), fg="#22c55e", bg="#0f172a").pack(pady=20)
        
        # Voice description
        gender_name = VOICE_GENDERS.get(voice_gender, {}).get("name", "Female")
        tone_name = VOICE_TONES.get(voice_tone, {}).get("name", "Medium")
        
        summary = f"""
Your AI is ready!

AI Name: {ai_name}
Wake Word: "{ai_name.lower()}"
AI Voice: {gender_name} - {tone_name}
Theme: {THEMES[self.user_data['theme']]['name']}
Voice Samples: {len(self.user_data['voice_samples'])}

How to use:
• Say "{ai_name}, open Chrome"
• Say "{ai_name}, remind me in 10 minutes"
• Say "{ai_name}, who are you?"

{ai_name} will respond:
"I am {ai_name}, personal assistant for {user_name}."
"""
        
        tk.Label(self.content, text=summary, font=("Arial", 11),
                 fg="#cbd5e1", bg="#0f172a", justify="left").pack(pady=10)
    
    def _finish(self):
        # Save user profile
        USER_FILE.parent.mkdir(parents=True, exist_ok=True)
        USER_FILE.write_text(json.dumps(self.user_data, indent=2))
        
        # Update config.yaml
        self._update_config()
        
        messagebox.showinfo(APP_NAME, f"Setup complete!\n\n{APP_NAME} will now start.")
        self.root.destroy()
    
    def _update_config(self):
        # Use the dynamic config generator
        from core.config_generator import generate_config, save_config
        
        # Get Piper voice based on gender + tone selection
        voice_gender = self.user_data.get("voice_gender", "female")
        voice_tone = self.user_data.get("voice_tone", "medium")
        piper_voice = PIPER_VOICES.get(voice_gender, {}).get(voice_tone, "en_US-amy-medium")
        voice_speed = VOICE_TONES.get(voice_tone, {}).get("speed", 1.0)
        
        config = generate_config(
            ai_name=self.user_data["ai_name"],
            user_name=self.user_data["user_name"],
            theme=self.user_data["theme"],
            voice_auth_enabled=len(self.user_data["voice_samples"]) >= 3,
            voice_gender=voice_gender,
            voice_tone=voice_tone,
            piper_voice=piper_voice,
            piper_length_scale=voice_speed,
        )
        
        save_config(config)
    
    def run(self):
        self.root.mainloop()


def check_first_run():
    """Check if this is the first run."""
    return not USER_FILE.exists()


def run_setup():
    """Run the setup wizard."""
    wizard = SetupWizard()
    wizard.run()


if __name__ == "__main__":
    run_setup()
