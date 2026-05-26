"""
Overnight model updater - no API key needed.
Detects GPU/RAM, pulls best free Ollama model, updates config, restarts ASTRA.
Run via Windows Task Scheduler at 3 AM.
"""
import subprocess
import sys
import os
import json
import time
import psutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Best free models by hardware tier (ordered best to fastest)
TIERS = {
    "high":   ["llama3.2:latest", "qwen2.5:7b-q4_K_M", "mistral:7b-q4_K_M", "phi3.5"],
    "mid":    ["qwen2.5:3b",      "phi3.5",             "gemma2:2b"],
    "low":    ["phi3.5",          "gemma2:2b",           "tinyllama"],
}

# Vision models for screen analysis
VISION_MODELS = ["moondream", "llava:7b-q4_0"]


def _detect_tier() -> str:
    # Try NVIDIA GPU
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            vram = int(r.stdout.strip().split("\n")[0].strip())
            if vram >= 8000:
                return "high"
            elif vram >= 4000:
                return "mid"
            return "low"
    except Exception:
        pass
    # CPU RAM fallback
    ram_gb = psutil.virtual_memory().total // (1024 ** 3)
    if ram_gb >= 16:
        return "mid"
    return "low"


def _local_models() -> list:
    try:
        r = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        lines = r.stdout.strip().split("\n")[1:]
        return [l.split()[0].split(":")[0] for l in lines if l.strip()]
    except Exception:
        return []


def _pull(model: str) -> bool:
    print(f"[Updater] Pulling {model}...")
    r = subprocess.run(["ollama", "pull", model], timeout=3600)
    return r.returncode == 0


def _update_config(model: str):
    import yaml
    cfg_path = ROOT / "config" / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    old = cfg["llm"]["model"]
    cfg["llm"]["model"] = model
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
    print(f"[Updater] Model updated: {old} -> {model}")
    # Write flag so ASTRA greets with new model name on next start
    (ROOT / "data" / "model_updated.flag").write_text(model)


def run():
    print(f"[Updater] Running at {time.strftime('%Y-%m-%d %H:%M')}")
    tier   = _detect_tier()
    local  = _local_models()
    targets= TIERS[tier]
    print(f"[Updater] Tier={tier} | Local={local} | Targets={targets}")

    from core.config_loader import load_config
    current = load_config()["llm"]["model"].split(":")[0]

    # Check if already on best model
    best_target = targets[0].split(":")[0]
    if best_target == current:
        print(f"[Updater] Already on best model: {current}")
    else:
        # Try to pull better model
        upgraded = False
        for model in targets:
            base = model.split(":")[0]
            if base == current:
                print(f"[Updater] Current model is already in tier. No upgrade needed.")
                upgraded = True
                break
            ok = _pull(model)
            if ok:
                _update_config(model)
                upgraded = True
                break
        if not upgraded:
            print("[Updater] No upgrade available this run.")

    # Also pull vision model if not present
    local_full = _local_models()
    has_vision = any("llava" in m or "moondream" in m for m in local_full)
    if not has_vision:
        print("[Updater] No vision model found. Pulling moondream (1.7GB)...")
        _pull("moondream")

    print("[Updater] Done.")


if __name__ == "__main__":
    run()
