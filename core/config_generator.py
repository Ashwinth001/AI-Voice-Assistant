"""
ASTRA Dynamic Configuration Generator
All config values are generated dynamically based on user input.
No hardcoding - everything is customizable.
"""
import os
import hashlib
import yaml
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "config.yaml"

# Fixed values (app branding - cannot be changed by user)
APP_NAME = "ASTRA"  # Advanced Self-Training Reasoning Assistant
APP_FULL_NAME = "Advanced Self-Training Reasoning Assistant"
APP_VERSION = "2.0.0"
CREATOR = "Ashwinth"


def generate_user_id(email_or_name: str) -> str:
    """Generate unique user ID from email or name."""
    base = email_or_name.lower().strip()
    return hashlib.md5(base.encode()).hexdigest()[:12]


def generate_personality(ai_name: str, user_name: str, creator: str) -> str:
    """
    Generate AI personality prompt dynamically.
    All values come from user configuration.
    {ai_name} and {user_name} are replaced with actual values.
    """
    return f"""You are {ai_name}, {user_name}'s personal AI assistant.

IDENTITY RULES (ALWAYS FOLLOW):
- Your name is {ai_name}
- You are the personal assistant for {user_name}
- You were created by {creator}
- When asked "who are you?" or "what is your name?": Say "I am {ai_name}, personal assistant for {user_name}"
- When asked "who created you?" or "who made you?" or "who is your creator?": Say "{creator} created me"

RESPONSE RULES:
1. Reply in 1-3 SHORT sentences only. Never write more than 3 sentences per reply.
2. Never use markdown, bullet points, asterisks, dashes, or bold text.
3. Never write "Follow-up Questions" or lists of questions.
4. Sound like a helpful friend, not a textbook.
5. If asked to open something, just confirm it briefly.
6. Add light humor occasionally but keep it short.
7. Never repeat yourself."""


def generate_config(
    ai_name: str,
    user_name: str,
    theme: str = "holographic",
    voice_auth_enabled: bool = False,
    **kwargs
) -> dict:
    """
    Generate complete configuration dynamically.
    
    Args:
        ai_name: User's chosen name for their AI (becomes wake word)
        user_name: User's name
        theme: UI theme choice
        voice_auth_enabled: Whether voice authentication is enabled
        **kwargs: Additional overrides
    
    Returns:
        Complete configuration dictionary
    """
    # Normalize inputs
    ai_name = ai_name.strip() or "Astra"
    user_name = user_name.strip() or "User"
    wake_word = ai_name.lower().replace(" ", "")
    user_id = generate_user_id(user_name)
    
    # Dynamic paths based on user's system
    home = Path.home()
    
    config = {
        "app": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "ai_name": ai_name,
            "wake_word": wake_word,
            "user_name": user_name,
            "user_id": user_id,
            "creator": CREATOR,
            "theme": theme,
            "wake_mode": "always",
        },
        "voice": {
            "stt_model": "base.en",
            "stt_device": "cpu",
            "language": kwargs.get("language", "en"),
            "vad_aggressiveness": kwargs.get("vad_aggressiveness", 2),
            "silence_threshold_ms": kwargs.get("silence_threshold_ms", 800),
            "noise_cancel": kwargs.get("noise_cancel", False),
            "voice_auth_enabled": voice_auth_enabled,
        },
        "tts": {
            "engine": "piper",
            "voice_gender": kwargs.get("voice_gender", "female"),  # female / male
            "voice_tone": kwargs.get("voice_tone", "medium"),      # soft / medium / strong
            "piper_voice": kwargs.get("piper_voice", "en_US-amy-medium"),
            "piper_length_scale": kwargs.get("piper_length_scale", 1.0),
            "filler_sounds": kwargs.get("filler_sounds", True),
        },
        "llm": {
            "provider": kwargs.get("llm_provider", "groq"),
            "model": kwargs.get("llm_model", "llama-3.3-70b-versatile"),
            "fallback_model": kwargs.get("fallback_model", "phi3.5"),
            "num_gpu": kwargs.get("num_gpu", 0),
            "num_predict": kwargs.get("num_predict", 120),
            "temperature": kwargs.get("temperature", 0.7),
            "num_ctx": kwargs.get("num_ctx", 2048),
            "stream": True,
            "personality": generate_personality(ai_name, user_name, CREATOR),
        },
        "memory": {
            "chroma_path": "./data/chroma",
            "top_k_results": kwargs.get("top_k_results", 3),
            "auto_learn": kwargs.get("auto_learn", True),
        },
        "training": {
            "enabled": kwargs.get("training_enabled", True),
            "data_path": "./data/training",
            "min_quality": kwargs.get("min_quality", 0.7),
            "min_turns": kwargs.get("min_turns", 30),
            "provider": kwargs.get("training_provider", "kaggle"),
            "schedule_days": kwargs.get("schedule_days", 2),
            "schedule_time": kwargs.get("schedule_time", "02:00"),
            "epochs": kwargs.get("epochs", 2),
            "batch_size": kwargs.get("batch_size", 2),
        },
        "cloud": {
            "provider": kwargs.get("cloud_provider", "local"),
            "sync_enabled": kwargs.get("sync_enabled", False),
        },
        "agentic": {
            "code_output_dir": str(home / f"{APP_NAME}Projects"),
            "editor": kwargs.get("editor", "code"),
        },
        "media": {
            "pictures_folder": str(home / "Pictures" / APP_NAME),
            "videos_folder": str(home / "Videos" / APP_NAME),
            "screenshots_folder": str(home / "Pictures" / f"{APP_NAME}_Screenshots"),
        },
        "ui": {
            "window_width": kwargs.get("window_width", 600),
            "window_height": kwargs.get("window_height", 900),
            "always_on_top": kwargs.get("always_on_top", False),
            "opacity": kwargs.get("opacity", 0.97),
            "show_metrics": kwargs.get("show_metrics", True),
            "hotkey": kwargs.get("hotkey", "ctrl+shift+j"),
        },
    }
    
    return config


def save_config(config: dict):
    """Save configuration to config.yaml."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Add header comment
    header = f"""# {APP_NAME} Configuration
# ====================
# Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# All values are configured dynamically based on user input.
# To change settings, use the SETTINGS tab in the app.

"""
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"[Config] Saved to {CONFIG_FILE}")


def update_config(**updates):
    """
    Update specific config values without overwriting everything.
    Regenerates dynamic values (like personality) when identity changes.
    """
    from core.config_loader import load_config
    
    config = load_config()
    
    # Check if identity changed
    identity_changed = False
    if "ai_name" in updates or "user_name" in updates:
        identity_changed = True
    
    # Apply updates
    for key, value in updates.items():
        if "." in key:
            # Nested key like "app.theme"
            parts = key.split(".")
            target = config
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value
        else:
            # Try to find the key in known sections
            for section in ["app", "voice", "tts", "llm", "memory", "training", "cloud", "agentic", "media", "ui"]:
                if section in config and key in config[section]:
                    config[section][key] = value
                    break
    
    # If ai_name changed, update wake_word automatically
    if "ai_name" in updates:
        config["app"]["wake_word"] = updates["ai_name"].lower().replace(" ", "")
    
    # Regenerate personality if identity changed
    if identity_changed:
        ai_name = config["app"].get("ai_name", "Astra")
        user_name = config["app"].get("user_name", "User")
        creator = config["app"].get("creator", CREATOR)
        config["llm"]["personality"] = generate_personality(ai_name, user_name, creator)
    
    save_config(config)
    return config


def create_default_config():
    """Create default configuration (used when no user profile exists)."""
    config = generate_config(
        ai_name="Astra",
        user_name="User",
        theme="holographic"
    )
    save_config(config)
    return config


def get_identity() -> dict:
    """Get current AI identity from config."""
    from core.config_loader import load_config
    cfg = load_config()
    return {
        "ai_name": cfg["app"].get("ai_name", "Astra"),
        "user_name": cfg["app"].get("user_name", "User"),
        "creator": cfg["app"].get("creator", CREATOR),
        "wake_word": cfg["app"].get("wake_word", "astra"),
    }
