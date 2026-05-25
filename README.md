# ARIA -- Adaptive Reasoning Intelligence Assistant

## Quick Start

```
1. Install Python 3.10+ from python.org
2. Install Ollama from ollama.ai
3. Double-click run.bat
4. Say "aria" to activate
```

## Choose your theme (config/config.yaml)
```yaml
app:
  theme: "holographic"   # sci-fi dark (like your image)
  # theme: "neon_glass"  # modern purple
  # theme: "minimal"     # clean Apple-style
  name: "ARIA"           # Change assistant name
  wake_word: "aria"      # Change wake word
  user_id: "ashwinth"    # Your unique ID
```

## Voice Commands
| Say | What happens |
|-----|-------------|
| "aria" | Wake up |
| "restart my PC" | Restarts computer |
| "open Chrome and search X" | Opens browser |
| "open D:/Projects" | Opens folder |
| "create a file called notes.txt" | Creates file |
| "write Python code to sort a list" | Writes + opens in VS Code |
| "remind me at 6pm to send the mail" | Sets reminder |
| "learn linear algebra" -> ingest PDF | Teaches from document |
| "good response" / "bad response" | Rates for training |
| "sleep" | Goes to standby |

## Training (local GPU)
Training runs automatically every Sunday 2AM via Task Scheduler.
To set up:
1. Open Task Scheduler
2. Create Basic Task -> "ARIA Training"
3. Trigger: Weekly, Sunday, 2:00 AM
4. Action: python.exe -> C:\path\to\ARIA\training\fine_tune.py

Or run manually:
```
python training/fine_tune.py
```

## Add knowledge
```python
# In Python or via voice: "load document D:/books/linear_algebra.pdf as linear algebra"
from core.memory import MemoryStore
m = MemoryStore("ashwinth")
m.ingest_document("D:/books/linear_algebra.pdf", "linear_algebra")
```

## Switch to Oracle Cloud (later)
Change config.yaml:
```yaml
cloud:
  provider: "oracle"
  oracle_namespace: "your-namespace"
  oracle_bucket: "aria-models"
  oracle_region: "ap-mumbai-1"
```

## Folder structure
```
ARIA/
+-- main.py              # Entry point
+-- run.bat              # Windows launcher
+-- config/config.yaml   # All settings here
+-- core/
|   +-- orchestrator.py  # Main pipeline
|   +-- noise_vad.py     # Noise cancel + VAD
|   +-- stt.py           # Speech to text
|   +-- tts.py           # Text to speech
|   +-- llm.py           # LLM + intent
|   +-- memory.py        # ChromaDB RAG
+-- agents/
|   +-- dispatcher.py    # PC/file/code actions
+-- ui/themes/
|   +-- holographic.py   # Theme 1 (sci-fi)
|   +-- neon_glass.py    # Theme 2 (neon)
|   +-- minimal_dark.py  # Theme 3 (clean)
+-- training/
|   +-- fine_tune.py     # LoRA self-training
+-- data/                # Created on first run
|   +-- chroma/          # ChromaDB memory
|   +-- training/        # JSONL training logs
|   +-- adapters/        # LoRA adapters
+-- assets/
    +-- hmm.wav           # Filler sound
    +-- voices/           # Piper TTS models
```
