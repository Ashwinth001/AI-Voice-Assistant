import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

# Module-level default (used by imports that do: from core.config_loader import cfg)
cfg = load_config()
