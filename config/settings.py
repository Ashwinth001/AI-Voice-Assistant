import os

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(BASE_DIR, "data")
MODELS_DIR= os.path.join(BASE_DIR, "models")
OLLAMA_MODELS_DIR = os.path.join(MODELS_DIR, "ollama")

# ── STT ────────────────────────────────────────────────────────
STT_BACKEND   = "whisper"       # "whisper" | "vosk"
WHISPER_MODEL = "tiny.en"       # tiny.en | base.en | small.en

# ── LLM ────────────────────────────────────────────────────────
OLLAMA_HOST      = "http://localhost:11434"
OLLAMA_MODEL     = "llama3.2"
OLLAMA_KEEP_ALIVE= "10m"
OLLAMA_TIMEOUT   = 30
MAX_HISTORY_TURNS= 6

# ── TTS ────────────────────────────────────────────────────────
TTS_BACKEND    = "edge"           # "edge" | "pyttsx3"
EDGE_TTS_VOICE = "en-US-GuyNeural"

# ── Wake / Sleep words ─────────────────────────────────────────
WAKE_WORDS  = ["jarvis", "hey jarvis", "ok jarvis", "activate"]
SLEEP_WORDS = ["sleep", "stand by", "go to sleep", "jarvis sleep"]

# ── Owner voice verification ───────────────────────────────────
VOICE_PRINT_SAMPLES  = 3
OWNER_THRESHOLD      = 0.70
VOICE_PRINT_PATH     = os.path.join(DATA_DIR, "voice_print.npy")

# ── Overlay ────────────────────────────────────────────────────
OVERLAY_CORNER = "bottom-right"   # top-left | top-right | bottom-left | bottom-right
OVERLAY_OPACITY= 0.93
OVERLAY_MARGIN = 20
OVERLAY_WIDTH  = 430
OVERLAY_HEIGHT = 570

# ── Knowledge / RAG ────────────────────────────────────────────
KNOWLEDGE_DB_PATH= os.path.join(DATA_DIR, "knowledge.db")
CHROMA_DIR       = os.path.join(DATA_DIR, "chroma")
CORRECTIONS_PATH = os.path.join(DATA_DIR, "corrections.json")

# ── Security ───────────────────────────────────────────────────
BLOCKLIST_PATH      = os.path.join(DATA_DIR, "blocklist.json")
SUSPICIOUS_KEYWORDS = [
    "keygen","crack","patch","hack","miner","trojan",
    "ransomware","spyware","backdoor","rootkit","exploit"
]

# ── General ────────────────────────────────────────────────────
ASSISTANT_NAME = "Jarvis"
LOG_LEVEL      = "INFO"
