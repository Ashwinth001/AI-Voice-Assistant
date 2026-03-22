# -*- coding: utf-8 -*-
"""Central configuration for the AI Voice Assistant."""

import os

import sys

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
VOICE_PRINT_PATH = os.path.join(DATA_DIR, "owner_voice_print.npz")
KNOWLEDGE_DB = os.path.join(DATA_DIR, "brain.db")
SECURE_VAULT = os.path.join(DATA_DIR, "secure_vault.db")

# Ensure dirs exist
for d in (DATA_DIR, MODELS_DIR):
    os.makedirs(d, exist_ok=True)

# Assistant name — change to whatever you want (e.g. Jarvis, Friday). Used in greetings and overlay.
ASSISTANT_NAME = "Jarvis"

# Optional: short phrase to start enrollment (e.g. "enroll" or "boss enroll"). Leave empty to use only the long phrase.
ENROLL_TRIGGER_SHORT = "enroll"

# Voice
SAMPLE_RATE = 16000
FRAME_MS = 30
VAD_AGGRESSIVENESS = 2  # 0-3, higher = more aggressive filtering
OWNER_VOICE_SIMILARITY_THRESHOLD = 0.15  # 0-1, min similarity to accept as owner (0.45 = stable default)
VOICE_PRINT_SAMPLES_NEEDED = 3  # number of voice samples to enroll
# When True: accept all voice input without verification (reliable responses). Set False for strict owner-only.
RELAXED_VOICE_MODE = True
# Min words/chars to treat as a real command (filters "i'm", "a", "but")
MIN_COMMAND_WORDS = 1
MIN_COMMAND_CHARS = 4
# Wait this many seconds after last speech before treating phrase as complete (so full sentence is used)
TRANSCRIPT_DEBOUNCE_SEC = 0.5
# Vosk STT: "auto" = prefer larger model (0.22) for accuracy, "large" = only 0.22, "small" = only 0.15
VOSK_MODEL_PREFERENCE = "small"
# Chunk length in seconds for Vosk (longer = more context, may improve accuracy; 0.5 = responsive)
VOSK_CHUNK_SEC = 0.8
# When True, log every raw transcript from Vosk to data/startup_log.txt (debug misrecognitions)
LOG_RAW_TRANSCRIPT = True
# STT backend: "whisper" = faster-whisper (more accurate, local), "vosk" = Vosk (lightweight)
STT_BACKEND = "whisper"
# Whisper (faster-whisper): model size (tiny.en, base.en, small.en = good accuracy/speed on CPU)
WHISPER_MODEL = "base.en"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
# How many seconds of audio to send to Whisper per chunk (longer = more context, slightly more delay)
WHISPER_CHUNK_SEC = 2.5

# Overlay UI
OVERLAY_OPACITY = 0.35
OVERLAY_WIDTH = 920
OVERLAY_HEIGHT = 420
OVERLAY_CORNER = "top_right"  # top_left, top_right, bottom_left, bottom_right
OVERLAY_MARGIN = 20

# Security
SCAN_INTERVAL_SEC = 300  # full app scan interval
MONITOR_INTERVAL_SEC = 10  # process list check
BLOCKLIST_DB = os.path.join(DATA_DIR, "blocklist.json")

# Local LLM (Ollama) for human-like thinking
OLLAMA_MODEL = "llama3.2"  # e.g. llama3.2, mistral, phi3

# Human-like TTS (Edge TTS voice; fallback: pyttsx3)
EDGE_TTS_VOICE = "en-US-JennyNeural"  # natural female; or en-US-GuyNeural, en-GB-SoniaNeural

# Learning
MAX_CORRECTIONS_HISTORY = 5000
MAX_KNOWLEDGE_ENTRIES = 100_000
CLASSIFICATION_TAGS = (
    "fact", "preference", "reminder", "command", "question",
    "correction", "vocabulary", "language", "security", "system"
)
