"""
ARIA - Nightly LoRA fine-tuner
Run via Windows Task Scheduler Sunday 2 AM
OR manually: python training/fine_tune.py
"""
import sys
import os
from pathlib import Path

# Fix sys.path so 'core' is importable regardless of where script is called from
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # Ensure relative paths work

import json
import datetime
from core.config_loader import cfg

USER_ID     = cfg["app"]["user_id"]
DATA_PATH   = ROOT / "data" / "training"
MIN_QUALITY = float(cfg["training"]["min_quality"])
MIN_TURNS   = int(cfg["training"]["min_turns"])
GPU_ENABLED = bool(cfg["training"]["gpu_enabled"])
CUDA_DEVICE = str(cfg["training"]["cuda_device"])
ADAPTER_DIR = ROOT / "data" / "adapters"
ADAPTER_DIR.mkdir(parents=True, exist_ok=True)


def load_training_data():
    jsonl_path = DATA_PATH / f"{USER_ID}_sessions.jsonl"
    if not jsonl_path.exists():
        print("[Train] No training data yet. Use ARIA first.")
        return []
    cutoff = datetime.datetime.now() - datetime.timedelta(days=7)
    turns = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
                ts = datetime.datetime.fromisoformat(t["timestamp"])
                if float(t.get("quality", 0)) >= MIN_QUALITY and ts > cutoff:
                    turns.append(t)
            except Exception:
                continue
    print(f"[Train] {len(turns)} quality turns from last 7 days")
    return turns


def format_dataset(turns):
    from datasets import Dataset
    records = []
    for t in turns:
        msgs = t.get("messages", [])
        if len(msgs) >= 2:
            records.append({
                "text": f"<|user|>\n{msgs[0]['content']}\n<|assistant|>\n{msgs[1]['content']}"
            })
    return Dataset.from_list(records)


def train():
    turns = load_training_data()
    if len(turns) < MIN_TURNS:
        print(f"[Train] Need {MIN_TURNS} turns, have {len(turns)}. Skipping.")
        return

    # Detect GPU
    use_gpu = False
    if GPU_ENABLED:
        try:
            import torch
            if torch.cuda.is_available():
                os.environ["CUDA_VISIBLE_DEVICES"] = CUDA_DEVICE
                use_gpu = True
                print(f"[Train] GPU available - using CUDA:{CUDA_DEVICE}")
            else:
                print("[Train] torch.cuda not available - falling back to CPU")
        except ImportError:
            print("[Train] torch not installed - using CPU")

    if not use_gpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        print("[Train] CPU mode (~3-5 hours)")

    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from transformers import TrainingArguments

    model_name = "unsloth/Phi-3.5-mini-instruct"
    print(f"[Train] Loading {model_name} ...")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=2048,
        load_in_4bit=True,
        device_map="auto" if use_gpu else "cpu",
    )

    # Load previous adapter if exists (cumulative - never forgets)
    prev = ADAPTER_DIR / f"{USER_ID}_latest"
    if prev.exists():
        print("[Train] Loading previous adapter - cumulative learning")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(prev))
        model = model.merge_and_unload()

    model = FastLanguageModel.get_peft_model(
        model,
        r=int(cfg["training"]["lora_r"]),
        lora_alpha=int(cfg["training"]["lora_alpha"]),
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
    )

    dataset = format_dataset(turns)
    print(f"[Train] Training on {len(dataset)} examples...")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        args=TrainingArguments(
            output_dir=str(ADAPTER_DIR / f"{USER_ID}_checkpoint"),
            num_train_epochs=int(cfg["training"]["epochs"]),
            per_device_train_batch_size=int(cfg["training"]["batch_size"]),
            gradient_accumulation_steps=4,
            fp16=use_gpu,
            bf16=False,
            learning_rate=2e-4,
            logging_steps=10,
            save_strategy="no",
            report_to="none",
        ),
    )
    trainer.train()

    # Save adapter
    adapter_path = ADAPTER_DIR / f"{USER_ID}_latest"
    model.save_pretrained(str(adapter_path))
    tokenizer.save_pretrained(str(adapter_path))

    # Version file
    vfile = ADAPTER_DIR / f"{USER_ID}_version.json"
    version = 1
    if vfile.exists():
        try:
            version = json.loads(vfile.read_text())["version"] + 1
        except Exception:
            pass
    vfile.write_text(json.dumps({
        "version": version,
        "trained": datetime.datetime.now().isoformat(),
        "turns": len(turns),
    }))
    print(f"[Train] Done. Adapter v{version} saved to {adapter_path}")

    # Create Ollama model
    mfile = ADAPTER_DIR / "Modelfile"
    mfile.write_text(
        f"FROM phi3.5\n"
        f"ADAPTER {adapter_path}\n"
        f'SYSTEM "{cfg[\"llm\"][\"personality\"].strip()}"\n'
    )
    import subprocess
    tag = f"aria-{USER_ID}-v{version}"
    result = subprocess.run(
        ["ollama", "create", tag, "-f", str(mfile)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"[Train] Ollama model '{tag}' created.")
        print(f"[Train] Update config.yaml: model: \"{tag}\"")
    else:
        print(f"[Train] Ollama create failed: {result.stderr[:200]}")


if __name__ == "__main__":
    print(f"[Train] Starting for user: {USER_ID}")
    print(f"[Train] Time: {datetime.datetime.now()}")
    train()
