# ASTRA - Advanced Self-Training Reasoning Assistant

## Personal Voice AI Assistant | FREE | Self-Learning | Offline Capable

**Cost: $0** (uses free APIs only - Groq, Kaggle GPU, no paid services)

```
=====================================================
     ASTRA v2.0 - Enterprise Edition
     Advanced Self-Training Reasoning Assistant
=====================================================
     AI Name: Configurable (becomes wake word)
     LLM: Groq Cloud / Ollama Local
     Training: Every 2 days (Kaggle FREE GPU)
     Cost: $0
=====================================================
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ASTRA MASTER ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        HARDWARE LAYER                                │   │
│  │  [Microphone] [Speakers] [Display] [System] [Network] [GPU/TPU]     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      INPUT PROCESSING LAYER                          │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │   │
│  │  │ Audio Input  │ │Screen Capture│ │ Wake Word    │ │Phone/Call  │  │   │
│  │  │ - VAD        │ │ - OCR        │ │ Detection    │ │ Detector   │  │   │
│  │  │ - Noise Red. │ │ - Vision AI  │ │ - Fuzzy Match│ │ - Auto Mute│  │   │
│  │  │ - Whisper STT│ │ - Moondream  │ │ - Variants   │ │ - Teams/Zoom│ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      INTELLIGENCE CORE                               │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │ FAST ROUTER - Pattern matching for instant commands           │   │   │
│  │  │ (open, search, remind, create, research, analyze)             │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │  ┌───────────────┐ ┌────────────────┐ ┌──────────────────────┐     │   │
│  │  │ LLM Provider  │ │ Intent Extract │ │ Memory / RAG         │     │   │
│  │  │ ┌───────────┐ │ │ - JSON output  │ │ - ChromaDB           │     │   │
│  │  │ │Groq Cloud │ │ │ - 25+ actions  │ │ - Sessions           │     │   │
│  │  │ │(200ms,free│ │ │ - Parameters   │ │ - Knowledge          │     │   │
│  │  │ └───────────┘ │ └────────────────┘ │ - Code snippets      │     │   │
│  │  │ ┌───────────┐ │                    │ - Web research        │     │   │
│  │  │ │Ollama Local│ │                    └──────────────────────┘     │   │
│  │  │ │(offline)  │ │                                                  │   │
│  │  │ └───────────┘ │                                                  │   │
│  │  └───────────────┘                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        ACTION LAYER                                  │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │ PC Control  │ │ Web Actions │ │ Productivity│ │ Learning    │   │   │
│  │  │ - Restart   │ │ - Browser   │ │ - Teams     │ │ - Research  │   │   │
│  │  │ - Shutdown  │ │ - Search    │ │ - Outlook   │ │ - Wikipedia │   │   │
│  │  │ - Files     │ │ - Scrape    │ │ - PowerPoint│ │ - GitHub    │   │   │
│  │  │ - Folders   │ │ - APIs      │ │ - Email     │ │ - Web scrape│   │   │
│  │  │ - Apps      │ │             │ │ - Calendar  │ │ - PDF/Docs  │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │ Code Gen    │ │ Reminders   │ │ System Info │ │ Screen Anal │   │   │
│  │  │ - Python    │ │ - Timer     │ │ - CPU/RAM   │ │ - OCR read  │   │   │
│  │  │ - JS/TS     │ │ - Scheduler │ │ - Disk      │ │ - Context   │   │   │
│  │  │ - Go/Rust   │ │ - Alerts    │ │ - Processes │ │ - Suggest   │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        OUTPUT LAYER                                  │   │
│  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐     │   │
│  │  │ TTS Engine       │ │ Visual UI        │ │ File Output      │     │   │
│  │  │ - Piper (local)  │ │ - Holographic    │ │ - Code files     │     │   │
│  │  │ - gTTS (online)  │ │ - Neon Glass     │ │ - Documents      │     │   │
│  │  │ - Multi-language │ │ - Minimal Dark   │ │ - Presentations  │     │   │
│  │  └──────────────────┘ └──────────────────┘ └──────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      LEARNING & CLOUD LAYER                          │   │
│  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐     │   │
│  │  │ Self-Training    │ │ Model Updates    │ │ Cloud Sync       │     │   │
│  │  │ - LoRA fine-tune │ │ - Nightly 3AM    │ │ - Oracle Cloud   │     │   │
│  │  │ - Quality filter │ │ - GPU detection  │ │ - User profiles  │     │   │
│  │  │ - Cumulative     │ │ - Auto-upgrade   │ │ - Cross-device   │     │   │
│  │  │ - Kaggle GPU/TPU │ │ - Vision models  │ │ - Backup/Restore │     │   │
│  │  └──────────────────┘ └──────────────────┘ └──────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Option 1: Windows Installer (Recommended)
```
1. Download ASTRA-Setup.exe
2. Run installer (adds to startup automatically)
3. Setup wizard opens - enter your name, AI name, theme
4. Say your AI name to start!
```

### Option 2: Manual Setup
```bash
1. Install Python 3.10+ from python.org
2. Double-click run.bat
3. Setup wizard opens on first run
4. Say your AI name followed by your command
```

## Configuration

### App Name vs AI Name (IMPORTANT)
- **App Name**: "ASTRA" (Advanced Self-Training Reasoning Assistant) - Fixed
- **AI Name**: User's choice (e.g., "Nova", "Alex", "Friday") - becomes the wake word
- **Creator**: Always "Ashwinth" - the AI will always say this when asked

### Example Identity Responses
If user **John** sets AI name to **Nova**:
- "Who are you?" → "I am Nova, personal assistant for John"
- "Who created you?" → "Ashwinth created me"

### AI Voice Selection
During installation, you can choose your AI's voice:
- **Voice Type**: Female / Male
- **Voice Style**: 
  - Soft - Gentle & calm
  - Medium - Natural & balanced  
  - Strong - Clear & assertive

You can change these anytime in Settings.

### config/config.yaml
```yaml
app:
  name: "ASTRA"          # Fixed app name (cannot change)
  ai_name: "Nova"        # User's AI name (becomes wake word)
  wake_word: "nova"      # Auto-set from ai_name
  user_name: "John"      # User's name
  creator: "Ashwinth"    # Fixed creator
  theme: "holographic"   # sci-fi / neon_glass / minimal

tts:
  voice_gender: "female" # female / male
  voice_tone: "medium"   # soft / medium / strong
  piper_voice: "..."     # Auto-set from gender + tone
```

## Voice Commands

### Wake Word Behavior (IMPORTANT!)
ASTRA uses wake word detection like Alexa/Siri/Google:
- **"always" mode (recommended)**: Say your AI name before EVERY command
  - Example: "Nova, open Chrome" / "Nova, what's the weather?"
  - AI will NOT respond if you're talking to someone else
- **"session" mode**: Say AI name once, then talk for 15 seconds
  - After 15 seconds of silence, returns to standby

### Auto-Mute During Calls
- ASTRA detects Teams, Zoom, Discord, Slack calls
- Automatically mutes during active calls
- Resumes listening when call ends

### Command Reference
(Replace "nova" with your AI name)

| Say | What happens |
|-----|-------------|
| "nova" | Wake up (greets you) |
| "nova, restart my PC" | Restarts computer |
| "nova, open Chrome and search X" | Opens browser |
| "nova, open D:/Projects" | Opens folder |
| "nova, create a file called notes.txt" | Creates file |
| "nova, write Python code to sort a list" | Writes + opens in VS Code |
| "nova, remind me at 6pm to send mail" | Sets reminder |
| "nova, learn about machine learning" | Learns from web forever |
| "nova, what am I doing" | Analyzes your screen |
| "nova, take a photo" | Captures from camera |
| "nova, record screen" | Records screen video |
| "nova, who are you?" | Speaks identity |
| "good response" / "bad response" | Rates for training |
| "nova, sleep" | Goes to standby |

## LLM Providers

### Option A: Groq Cloud (Recommended - No Install)
```bash
# Get free API key at https://console.groq.com (2 minutes)
# Set environment variable:
set GROQ_API_KEY=your_key_here

# Uses llama-3.3-70b - much better than local phi3.5
# 500 free requests/day, 200ms response time
```

### Option B: Ollama Local (Offline)
```bash
# Install Ollama from https://ollama.com
# ASTRA auto-pulls the best model for your GPU
# Works completely offline
```

## Training Pipeline

### Automatic Training (FREE - Kaggle GPU)
- **Schedule**: Every 2 days (configurable)
- **Provider**: Kaggle FREE GPU/TPU (no local GPU needed!)
- **Cost**: $0 (Kaggle free tier: 30 hours/week GPU)
- **Cumulative**: Never forgets - builds on previous training

### How Training Works
1. ASTRA logs all conversations locally
2. Every 2 days, uploads training data to Kaggle
3. Kaggle trains on FREE GPU (T4/P100)
4. Downloads improved model automatically
5. AI gets smarter with every training cycle

### Manual Training
```bash
# Upload data and start Kaggle training
python training/kaggle_train.py --upload

# Check training status
python training/kaggle_train.py --status

# Download trained model
python training/kaggle_train.py --download
```

### Training Configuration
```yaml
training:
  provider: "kaggle"     # FREE GPU!
  schedule_days: 2       # Train every 2 days
  # provider: "local"    # Only if you have GPU
```

## Oracle Cloud Deployment

### Step-by-Step Deployment Guide

#### Prerequisites
1. Oracle Cloud account (free tier available)
2. OCI CLI installed and configured
3. Docker installed locally

#### Step 1: Create Oracle Cloud Resources
```bash
# Run setup script
python cloud/oracle_setup.py

# This creates:
# - Compute instance (VM.Standard.E4.Flex)
# - Object Storage bucket
# - Container Registry
# - API Gateway
```

#### Step 2: Build and Push Docker Image
```bash
docker build -t astra-server .
docker tag astra-server <region>.ocir.io/<namespace>/astra-server:latest
docker push <region>.ocir.io/<namespace>/astra-server:latest
```

#### Step 3: Deploy to Oracle
```bash
python cloud/deploy.py --env production
```

#### Step 4: Configure Client
```yaml
# config/config.yaml
cloud:
  provider: "oracle"
  api_endpoint: "https://your-gateway.oracle.com/astra"
  sync_enabled: true
```

## Web Portal (User Registration)

### Features
- User registration with email verification
- Choose AI name and theme
- Select features needed
- Cross-device sync
- Training data management

### Access
After deployment: `https://your-domain.com/register`

## Offline Mode

**Ollama is NOT required!** ASTRA works offline with:

### What Works Offline (No Internet)
- All PC control (open files, folders, apps)
- Reminders and timers
- Take photos, record video, screenshots
- Previous knowledge (from ChromaDB)
- Conversations from memory
- Piper TTS (local voice)

### What Needs Internet
- New web research ("learn about X")
- Groq LLM responses (falls back to memory)
- Cloud sync

### Offline Response Strategy
When offline, ASTRA uses:
1. **Cached responses** from previous conversations
2. **Stored knowledge** from past research
3. **Basic commands** (always work locally)

```
User: "Nova, open Chrome"       → Works offline ✓
User: "Nova, remind me..."      → Works offline ✓  
User: "Nova, take screenshot"   → Works offline ✓
User: "Nova, research AI"       → Needs internet ✗
```

## Latency Optimization

### Why Local Can Be Slow
- Ollama phi3.5 on CPU: 10-30 seconds per response
- Solution: Use Groq Cloud API

### Groq Cloud Benefits
- 200ms response time (vs 30s local)
- Better model (llama-3.3-70b vs phi3.5)
- Free 500 requests/day
- No GPU required

### Best Performance Setup
```yaml
# Use Groq for fast responses + Ollama for offline fallback
llm:
  provider: "groq"  # Primary
  fallback: "ollama"  # When offline
```

## Folder Structure

```
ASTRA/
├── main.py              # Entry point
├── run.bat              # Windows launcher
├── setup.py             # Installer script
├── Dockerfile           # Container build
├── config/
│   └── config.yaml      # All settings
├── core/
│   ├── orchestrator.py  # Main pipeline with wake word
│   ├── noise_vad.py     # Noise cancel + VAD
│   ├── stt.py           # Speech to text (Whisper)
│   ├── tts.py           # Text to speech (Piper/gTTS)
│   ├── llm.py           # LLM (Groq/Ollama)
│   ├── memory.py        # ChromaDB RAG
│   ├── phone_detector.py# Call detection
│   ├── screen_analyzer.py# Screen OCR/vision
│   ├── web_learner.py   # Research pipeline
│   └── model_updater.py # Nightly model updates
├── agents/
│   ├── dispatcher.py    # Action routing
│   ├── windows_integration.py  # Teams/Outlook
│   └── mcp_tools.py     # MCP protocol tools
├── ui/themes/
│   ├── holographic.py   # Sci-fi theme
│   ├── neon_glass.py    # Modern theme
│   └── minimal_dark.py  # Clean theme
├── training/
│   ├── fine_tune.py     # Local LoRA training
│   └── kaggle_train.py  # Cloud GPU training
├── cloud/
│   ├── oracle_setup.py  # Cloud infrastructure
│   ├── deploy.py        # Deployment script
│   └── api_server.py    # Cloud API
├── web/
│   ├── app.py           # Flask web portal
│   └── templates/       # Registration pages
├── data/
│   ├── chroma/          # ChromaDB memory
│   ├── training/        # JSONL logs
│   └── adapters/        # LoRA adapters
└── assets/
    ├── hmm.wav          # Filler sound
    └── voices/          # Piper TTS models
```

## Troubleshooting

### "ASTRA responds when I'm on a call"
- Check if `wake_mode: "always"` is set in config.yaml
- Ensure Teams/Zoom/Discord is in the process detection list

### "Slow responses"
- Use Groq Cloud API (200ms vs 30s local)
- Or get a GPU with 8GB+ VRAM

### "Can't hear my voice"
- Check microphone permissions in Windows
- Increase `silence_threshold_ms` to 1200

### "Wake word not detected"
- Try speaking clearly with your AI name
- Check `vad_aggressiveness` (lower = more sensitive)

## License

MIT License - Use freely for personal and commercial projects.
