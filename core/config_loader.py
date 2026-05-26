"""
ASTRA Configuration Loader
Loads config with fallbacks for missing values.
"""
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"

# Default values for all config keys (used as fallbacks)
DEFAULTS = {
    "app": {
        "name": "ASTRA",  # Advanced Self-Training Reasoning Assistant
        "version": "2.0.0",
        "ai_name": "Astra",
        "wake_word": "astra",
        "user_name": "User",
        "user_id": "default",
        "creator": "Ashwinth",
        "theme": "holographic",
        "wake_mode": "always",
    },
    "voice": {
        "stt_model": "base.en",
        "stt_device": "cpu",
        "language": "en",
        "vad_aggressiveness": 2,
        "silence_threshold_ms": 800,
        "noise_cancel": False,
        "voice_auth_enabled": False,
    },
    "tts": {
        "engine": "piper",
        "voice_gender": "female",
        "voice_tone": "medium",
        "piper_voice": "en_US-amy-medium",
        "piper_length_scale": 1.0,
        "filler_sounds": True,
    },
    "llm": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "fallback_model": "phi3.5",
        "num_gpu": 0,
        "num_predict": 120,
        "temperature": 0.7,
        "num_ctx": 2048,
        "stream": True,
        "personality": "",
    },
    "memory": {
        "chroma_path": "./data/chroma",
        "top_k_results": 3,
        "auto_learn": True,
    },
    "training": {
        "enabled": True,
        "data_path": "./data/training",
        "min_quality": 0.7,
        "min_turns": 30,
        "provider": "kaggle",
        "schedule_days": 2,
        "schedule_time": "02:00",
        "epochs": 2,
        "batch_size": 2,
    },
    "cloud": {
        "provider": "local",
        "sync_enabled": False,
    },
    "agentic": {
        "code_output_dir": str(Path.home() / "ASTRAProjects"),
        "editor": "code",
    },
    "media": {
        "pictures_folder": str(Path.home() / "Pictures" / "ASTRA"),
        "videos_folder": str(Path.home() / "Videos" / "ASTRA"),
        "screenshots_folder": str(Path.home() / "Pictures" / "ASTRA_Screenshots"),
    },
    "ui": {
        "window_width": 600,
        "window_height": 900,
        "always_on_top": False,
        "opacity": 0.97,
        "show_metrics": True,
        "hotkey": "ctrl+shift+j",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif value is not None and value != "":
            result[key] = value
    return result


def load_config() -> dict:
    """
    Load configuration with fallbacks for missing values.
    If a config value is missing or empty, uses default.
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            file_config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print("[Config] config.yaml not found, using defaults")
        file_config = {}
    except Exception as e:
        print(f"[Config] Error loading config: {e}, using defaults")
        file_config = {}
    
    # Merge with defaults (file values override defaults)
    config = _deep_merge(DEFAULTS, file_config)
    
    # Auto-generate personality if empty
    if not config["llm"].get("personality"):
        ai_name = config["app"].get("ai_name", "Astra")
        user_name = config["app"].get("user_name", "User")
        creator = config["app"].get("creator", "Ashwinth")
        config["llm"]["personality"] = f"""You are {ai_name}, {user_name}'s personal AI assistant.

IDENTITY RULES (ALWAYS FOLLOW):
- Your name is {ai_name}
- You are the personal assistant for {user_name}
- You were created by {creator}
- When asked "who are you?": "I am {ai_name}, personal assistant for {user_name}"
- When asked "who created you?": "{creator} created me"

RESPONSE RULES:
1. Reply in 1-3 SHORT sentences only. Never write more than 3 sentences per reply.
2. Never use markdown, bullet points, asterisks, dashes, or bold text.
3. Never write "Follow-up Questions" or lists of questions.
4. Sound like a helpful friend, not a textbook.
5. If asked to open something, just confirm it briefly.
6. Add light humor occasionally but keep it short.
7. Never repeat yourself."""
    
    # Auto-set wake_word from ai_name if empty
    if not config["app"].get("wake_word"):
        config["app"]["wake_word"] = config["app"].get("ai_name", "astra").lower()
    
    return config


def save_config(cfg: dict):
    """Save configuration to file."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get(key: str, default=None):
    """Get a config value by dot-notation key (e.g., 'app.ai_name')."""
    config = load_config()
    parts = key.split(".")
    value = config
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return default
    return value if value is not None else default


# Module-level default (used by imports that do: from core.config_loader import cfg)
cfg = load_config()
