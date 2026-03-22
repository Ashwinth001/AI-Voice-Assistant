# Windows AI Voice Assistant

A **Windows-based AI Voice Assistant** that behaves like a friend and assistant. It runs **entirely on your PC**—no cloud, no external APIs. It learns from you, accepts **only your voice**, and helps secure your system.

## Features

- **Owner-only voice** — Enrolls your voice once; only your voice is accepted for commands.
- **System overlay UI** — Faded, always-on-top widget in a corner that does not block other apps.
- **Think like a human** — Uses a **local LLM (Ollama)** for natural conversation, reasoning, and short voice-friendly replies. Uses your stored knowledge and recent conversation as context.
- **Speak like a human** — Uses **Edge TTS** (Microsoft’s natural voices) for realistic speech; falls back to pyttsx3 if offline.
- **Self-learning** — Learns facts, preferences, corrections, and vocabulary locally. Classifies and retrieves information. Learns from mistakes via corrections.
- **Security** — Monitors running processes, scans installed apps, detects suspicious/blocklisted items. All data stays on your machine.

## Requirements

- **Windows 10/11**
- **Python 3.10+**
- Microphone
- ~500 MB free space (Vosk model)
- **Ollama** installed and running for human-like thinking (optional; falls back to keyword brain if not available)
- Internet for **Edge TTS** (human-like speech); pyttsx3 works offline

## Setup

### 1. Create virtual environment and install dependencies

```powershell
cd "c:\Users\rashw\Desktop\New AI Assistant"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Speech recognition (STT)

**Option A — Whisper (recommended, more accurate)**  
Install faster-whisper; the app will use it by default:

```powershell
pip install faster-whisper
```

The first run will download a small English model (e.g. `base.en`). In `config/settings.py` you can set `STT_BACKEND = "whisper"` and `WHISPER_MODEL = "base.en"` (or `tiny.en` for faster, `small.en` for better accuracy).

**Option B — Vosk (lightweight, offline)**  
If you prefer Vosk or don’t install Whisper, download a small English model:

- [vosk-model-small-en-us-0.15](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip) (~40 MB)

Extract the **folder** (e.g. `vosk-model-small-en-us-0.15`) into the project’s `models` folder. Then set `STT_BACKEND = "vosk"` in `config/settings.py`.

### 3. (Optional) Ollama for human-like thinking

Install [Ollama](https://ollama.com), then pull a small model:

```powershell
ollama pull llama3.2
```

If Ollama is not running or no model is pulled, the assistant still works using the local keyword brain.

### 4. Run the assistant

```powershell
python main.py
```

- **First run:** Say **“I am enrolling myself as your boss or owner”** (or “setup owner”), then say **any phrase 3 times** (e.g. “I am the owner”) to enroll your voice. After that, only your voice will be accepted.
- The **overlay** appears in the bottom-right (faded). It shows status and the last line.
- **Examples:** “Remember that I like coffee”, “What does X mean?”, “Actually I meant Y” (correction). With Ollama running, you can chat naturally and get human-like replies.

## Configuration

Edit `config/settings.py`:

- **Overlay:** `OVERLAY_OPACITY`, `OVERLAY_CORNER`, `OVERLAY_MARGIN`
- **Voice:** `OWNER_VOICE_SIMILARITY_THRESHOLD`, `VOICE_PRINT_SAMPLES_NEEDED`
- **LLM:** `OLLAMA_MODEL` (e.g. `llama3.2`, `mistral`, `phi3`)
- **TTS:** `EDGE_TTS_VOICE` (e.g. `en-US-JennyNeural`, `en-US-GuyNeural`, `en-GB-SoniaNeural`)
- **Security:** `SCAN_INTERVAL_SEC`, `MONITOR_INTERVAL_SEC`

## Data and privacy

- All data is stored under the project’s `data/` folder (voice print, knowledge DB, blocklist).
- **Ollama** runs locally; conversation and knowledge stay on your machine.
- **Edge TTS** sends only the text to be spoken to Microsoft’s TTS service (no conversation history). For 100% offline speech, the app falls back to pyttsx3.
- The assistant only acts on commands after verifying the owner’s voice (when enrollment is done).

## Security module

- **Process monitor** — Periodically lists running processes and checks names/hashes against a local blocklist.
- **Suspicious names** — Heuristic detection of risky names (e.g. keygen, crack, miner) without cloud.
- **Blocklist** — You can add process names or paths to `data/blocklist.json` (or via a future “block this” voice command).

## Limitations

- **Ollama** must be running (and a model pulled) for human-like conversation; otherwise the assistant uses the local keyword brain.
- **STT** — Vosk is good but not perfect; quiet or noisy environments may reduce accuracy.
- **Owner verification** — Based on a local voice print; very similar voices might occasionally be accepted.

You can extend the assistant by adding more intents in `main.py` and more tags/classification in `core/brain.py`.
