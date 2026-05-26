"""
ASTRA Offline Mode Handler
Enables limited functionality when internet is unavailable.

Offline Capabilities:
- Local Ollama LLM (if installed)
- Piper TTS (local voice)
- All PC control (files, apps, restart, etc.)
- ChromaDB memory (cached knowledge)
- Past conversation context

Disabled When Offline:
- Groq API
- Web research
- gTTS (falls back to Piper)
- Cloud sync
"""
import socket
import time
import threading
from typing import Callable
from core.config_loader import load_config


class OfflineManager:
    """
    Manages offline mode detection and capability switching.
    """
    
    def __init__(self, 
                 on_offline: Callable = None,
                 on_online: Callable = None):
        self._online = True
        self._last_check = 0
        self._check_interval = 30  # seconds
        
        self.on_offline = on_offline or (lambda: None)
        self.on_online = on_online or (lambda: None)
        
        self._running = False
        
    def start(self):
        """Start background connection monitoring."""
        self._running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
    
    def stop(self):
        """Stop monitoring."""
        self._running = False
    
    def is_online(self) -> bool:
        """Check if currently online."""
        return self._online
    
    def check_connection(self, timeout: float = 3.0) -> bool:
        """
        Check internet connectivity by trying to connect to reliable hosts.
        Uses multiple fallback hosts to avoid false negatives.
        """
        hosts = [
            ("8.8.8.8", 53),         # Google DNS
            ("1.1.1.1", 53),         # Cloudflare DNS
            ("208.67.222.222", 53),  # OpenDNS
        ]
        
        for host, port in hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((host, port))
                sock.close()
                return True
            except (socket.timeout, socket.error):
                continue
        
        return False
    
    def _monitor_loop(self):
        """Background loop to monitor connection status."""
        while self._running:
            now = time.time()
            if now - self._last_check >= self._check_interval:
                self._last_check = now
                
                was_online = self._online
                self._online = self.check_connection()
                
                # State changed
                if was_online and not self._online:
                    print("[Offline] Internet connection lost - switching to offline mode")
                    self.on_offline()
                elif not was_online and self._online:
                    print("[Offline] Internet connection restored - switching to online mode")
                    self.on_online()
            
            time.sleep(5)
    
    def get_available_features(self) -> dict:
        """
        Get dictionary of available features based on connection status.
        """
        cfg = load_config()
        
        if self._online:
            return {
                "llm": ["groq", "ollama"],
                "tts": ["piper", "gtts"],
                "stt": ["whisper"],
                "research": True,
                "cloud_sync": True,
                "web_search": True,
                "pc_control": True,
                "memory": True,
            }
        else:
            # Offline mode
            return {
                "llm": ["ollama"],  # Only local
                "tts": ["piper"],   # Only local
                "stt": ["whisper"], # Local
                "research": False,  # No web access
                "cloud_sync": False,
                "web_search": False,
                "pc_control": True,  # Still works
                "memory": True,      # ChromaDB is local
            }


class OfflineLLMFallback:
    """
    LLM wrapper that handles offline scenarios.
    Falls back to cached responses when appropriate.
    """
    
    def __init__(self, llm_engine, memory_store):
        self.llm = llm_engine
        self.memory = memory_store
        self.offline_manager = OfflineManager()
        self._cached_responses = {}
    
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate response with offline fallback.
        """
        if self.offline_manager.is_online():
            # Try normal generation
            try:
                return self.llm.simple_query(prompt)
            except Exception as e:
                print(f"[Offline] LLM error, trying offline mode: {e}")
        
        # Offline mode - try local Ollama
        if self.llm.use_ollama:
            try:
                return self.llm.simple_query(prompt)
            except Exception:
                pass
        
        # Last resort - use memory context
        context = self.memory.get_context(prompt)
        if context:
            return f"Based on what I remember: {context}"
        
        return ("I'm currently offline and don't have this information cached. "
                "Please try again when connected to the internet.")
    
    def get_cached_response(self, query: str) -> str:
        """
        Try to find a relevant cached response from memory.
        """
        # Search in session history
        try:
            results = self.memory.sessions.query(
                query_texts=[query],
                n_results=3
            )
            if results and results["documents"]:
                # Return most relevant cached response
                return results["documents"][0][0]
        except Exception:
            pass
        
        return None


class OfflineKnowledgeBase:
    """
    Offline knowledge base using ChromaDB.
    Stores important information for offline access.
    """
    
    def __init__(self, memory_store):
        self.memory = memory_store
        
        # Essential knowledge to cache
        self._essential_topics = [
            "system commands",
            "file operations",
            "common questions",
            "user preferences",
        ]
    
    def cache_essential(self, topic: str, content: str):
        """
        Cache essential information for offline access.
        """
        self.memory.knowledge.upsert(
            documents=[content],
            metadatas=[{"topic": topic, "offline_essential": True}],
            ids=[f"offline_cache_{topic.replace(' ', '_')}"]
        )
    
    def get_offline_knowledge(self, query: str) -> str:
        """
        Retrieve knowledge suitable for offline use.
        """
        try:
            results = self.memory.knowledge.query(
                query_texts=[query],
                n_results=5,
                where={"offline_essential": True}
            )
            if results and results["documents"]:
                return " | ".join(results["documents"][0])
        except Exception:
            pass
        
        return ""
    
    def pre_cache_common_queries(self):
        """
        Pre-cache responses to common queries for offline use.
        """
        common = [
            ("how to restart", "To restart your PC, say your AI name followed by 'restart my PC' or use Ctrl+Alt+Del."),
            ("how to open file", "Say your AI name followed by 'open' and the file path. Example: 'Nova, open D:/Documents/notes.txt'"),
            ("how to search", "Say your AI name followed by 'search for' and your query. Example: 'Nova, search for Python tutorials'"),
            ("reminder", "Say your AI name followed by 'remind me in X minutes to do Y'. Example: 'Nova, remind me in 10 minutes to call John'"),
            ("write code", "Say your AI name followed by 'write Python code to do X'. The code will be saved and opened in VS Code."),
        ]
        
        for topic, content in common:
            self.cache_essential(topic, content)
        
        print(f"[Offline] Pre-cached {len(common)} common queries")


def create_offline_response(query: str) -> str:
    """
    Generate a helpful response when completely offline.
    """
    query_lower = query.lower()
    
    # PC control commands still work offline
    if any(w in query_lower for w in ["open", "restart", "shutdown", "file", "folder"]):
        return "I can do that. This command works offline."
    
    # Remind works
    if "remind" in query_lower:
        return "I can set that reminder for you."
    
    # Research doesn't work
    if any(w in query_lower for w in ["research", "search", "learn about", "find out"]):
        return ("I can't research topics while offline. "
                "However, I can answer from my cached knowledge if I've learned about this before.")
    
    # Default offline message
    return ("I'm currently offline and have limited capabilities. "
            "I can still control your PC, set reminders, and answer from cached knowledge. "
            "For web research or cloud features, please reconnect to the internet.")
