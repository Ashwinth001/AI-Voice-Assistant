"""
ASTRA Kaggle Cloud Training
Uses Kaggle's free GPU/TPU for training when local GPU unavailable.

Usage:
  python training/kaggle_train.py --upload    # Upload data and start training
  python training/kaggle_train.py --status    # Check training status
  python training/kaggle_train.py --download  # Download trained model

Prerequisites:
  1. Create Kaggle account: https://www.kaggle.com
  2. Get API token: Account -> API -> Create New Token
  3. Save kaggle.json to ~/.kaggle/
"""
import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config_loader import cfg

USER_ID = cfg["app"]["user_id"]
DATA_DIR = ROOT / "data" / "training"
ADAPTERS_DIR = ROOT / "data" / "adapters"


KAGGLE_NOTEBOOK = '''
# ASTRA Cloud Training Notebook
# Auto-generated - runs on Kaggle GPU/TPU

import os
import json
from pathlib import Path

# Install dependencies
!pip install -q unsloth transformers datasets peft trl accelerate bitsandbytes

# Download training data (uploaded as dataset)
!kaggle datasets download -d {username}/astra-training-data
!unzip -q astra-training-data.zip -d /kaggle/working/data

# Load data
data_file = Path("/kaggle/working/data/training_data.json")
training_data = json.loads(data_file.read_text())

print(f"Loaded {{len(training_data)}} training examples")

# Training code
from unsloth import FastLanguageModel
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

model_name = "unsloth/Phi-3.5-mini-instruct"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=2048,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    lora_dropout=0.05,
)

# Format dataset
records = []
for t in training_data:
    msgs = t.get("messages", [])
    if len(msgs) >= 2:
        records.append({{
            "text": f"<|user|>\\n{{msgs[0]['content']}}\\n<|assistant|>\\n{{msgs[1]['content']}}"
        }})

dataset = Dataset.from_list(records)
print(f"Training on {{len(dataset)}} examples")

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    args=TrainingArguments(
        output_dir="/kaggle/working/output",
        num_train_epochs=2,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        fp16=True,
        learning_rate=2e-4,
        logging_steps=10,
        save_strategy="epoch",
        report_to="none",
    ),
)

trainer.train()

# Save adapter
adapter_path = "/kaggle/working/adapter"
model.save_pretrained(adapter_path)
tokenizer.save_pretrained(adapter_path)

# Zip for download
!zip -r /kaggle/working/astra_adapter.zip /kaggle/working/adapter

print("Training complete! Download astra_adapter.zip from output.")
'''


def check_kaggle_cli():
    """Check if Kaggle CLI is available."""
    try:
        result = subprocess.run(["kaggle", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[Kaggle] CLI: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("[Kaggle] CLI not found. Install with: pip install kaggle")
    print("[Kaggle] Then add your API token to ~/.kaggle/kaggle.json")
    return False


def prepare_training_data():
    """Prepare training data for upload."""
    data_file = DATA_DIR / f"{USER_ID}_sessions.jsonl"
    if not data_file.exists():
        print("[Kaggle] No training data found. Use ASTRA first to generate data.")
        return None
    
    # Load and filter data
    turns = []
    with open(data_file, encoding="utf-8") as f:
        for line in f:
            try:
                t = json.loads(line.strip())
                if float(t.get("quality", 0)) >= 0.7:
                    turns.append(t)
            except Exception:
                continue
    
    if len(turns) < 30:
        print(f"[Kaggle] Need at least 30 quality turns, have {len(turns)}")
        return None
    
    # Save for upload
    upload_dir = ROOT / "data" / "kaggle_upload"
    upload_dir.mkdir(exist_ok=True)
    
    (upload_dir / "training_data.json").write_text(json.dumps(turns, indent=2))
    
    # Create dataset metadata
    metadata = {
        "title": "astra-training-data",
        "id": f"{get_kaggle_username()}/astra-training-data",
        "licenses": [{"name": "CC0-1.0"}],
    }
    (upload_dir / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2))
    
    print(f"[Kaggle] Prepared {len(turns)} training examples")
    return upload_dir


def get_kaggle_username():
    """Get Kaggle username from config."""
    kaggle_config = Path.home() / ".kaggle" / "kaggle.json"
    if kaggle_config.exists():
        data = json.loads(kaggle_config.read_text())
        return data.get("username", "astra-user")
    return "astra-user"


def upload_training_data():
    """Upload training data to Kaggle."""
    upload_dir = prepare_training_data()
    if not upload_dir:
        return False
    
    print("[Kaggle] Uploading training data...")
    result = subprocess.run(
        ["kaggle", "datasets", "create", "-p", str(upload_dir)],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        print("[Kaggle] Data uploaded successfully")
        return True
    else:
        # Try update if dataset exists
        result = subprocess.run(
            ["kaggle", "datasets", "version", "-p", str(upload_dir), "-m", "Updated training data"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("[Kaggle] Data updated successfully")
            return True
    
    print(f"[Kaggle] Upload failed: {result.stderr}")
    return False


def create_notebook():
    """Create and upload training notebook."""
    username = get_kaggle_username()
    notebook_content = KAGGLE_NOTEBOOK.format(username=username)
    
    notebook_dir = ROOT / "data" / "kaggle_notebook"
    notebook_dir.mkdir(exist_ok=True)
    
    # Create notebook
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": notebook_content.split("\n"),
                "execution_count": None,
                "outputs": [],
                "metadata": {}
            }
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    
    (notebook_dir / "astra-training.ipynb").write_text(json.dumps(notebook, indent=2))
    
    # Metadata for push
    metadata = {
        "id": f"{username}/astra-training",
        "title": "ASTRA Training",
        "code_file": "astra-training.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [f"{username}/astra-training-data"],
        "competition_sources": [],
        "kernel_sources": [],
    }
    
    (notebook_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
    
    print("[Kaggle] Pushing training notebook...")
    result = subprocess.run(
        ["kaggle", "kernels", "push", "-p", str(notebook_dir)],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        print("[Kaggle] Notebook pushed. It will run automatically.")
        print(f"[Kaggle] Check status at: https://www.kaggle.com/{username}/astra-training")
        return True
    
    print(f"[Kaggle] Push failed: {result.stderr}")
    return False


def check_status():
    """Check training status."""
    username = get_kaggle_username()
    print(f"[Kaggle] Checking status for {username}/astra-training...")
    
    result = subprocess.run(
        ["kaggle", "kernels", "status", f"{username}/astra-training"],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"[Kaggle] Could not get status: {result.stderr}")


def download_model():
    """Download trained model from Kaggle."""
    username = get_kaggle_username()
    
    print("[Kaggle] Downloading trained adapter...")
    download_dir = ROOT / "data" / "kaggle_download"
    download_dir.mkdir(exist_ok=True)
    
    result = subprocess.run(
        ["kaggle", "kernels", "output", f"{username}/astra-training", "-p", str(download_dir)],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print(f"[Kaggle] Download failed: {result.stderr}")
        return False
    
    # Extract adapter
    adapter_zip = download_dir / "astra_adapter.zip"
    if adapter_zip.exists():
        print("[Kaggle] Extracting adapter...")
        shutil.unpack_archive(adapter_zip, ADAPTERS_DIR / f"{USER_ID}_kaggle")
        print(f"[Kaggle] Adapter saved to: {ADAPTERS_DIR / f'{USER_ID}_kaggle'}")
        
        # Update config
        print("[Kaggle] Update config.yaml to use the new adapter.")
        return True
    
    print("[Kaggle] No adapter found in output")
    return False


def main():
    parser = argparse.ArgumentParser(description="ASTRA Kaggle Cloud Training")
    parser.add_argument("--upload", action="store_true", help="Upload data and start training")
    parser.add_argument("--status", action="store_true", help="Check training status")
    parser.add_argument("--download", action="store_true", help="Download trained model")
    args = parser.parse_args()
    
    if not check_kaggle_cli():
        return
    
    if args.upload:
        if upload_training_data():
            create_notebook()
    elif args.status:
        check_status()
    elif args.download:
        download_model()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
