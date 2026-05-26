"""
Orchestrator v5 - Wake word REQUIRED for every command.
- Only responds when you say the wake word (like Alexa/Siri)
- Auto-mutes during phone calls (Teams, Zoom, Discord)
- Deactivates after 15 seconds of silence
- No more accidental responses when talking to others
"""
import threading
import time
from core.config_loader import load_config
from core.fast_commands import try_fast_route


class ARIAOrchestrator:
    def __init__(self, on_state_change=None, on_transcript=None, on_response=None):
        self._cfg      = load_config()
        self.app_name  = self._cfg["app"].get("name", "ASTRA")
        self.ai_name   = self._cfg["app"].get("ai_name", "Astra")  # User's chosen AI name
        self.wake_word = self._cfg["app"].get("wake_word", self.ai_name.lower()).lower().strip()
        self.user_name = self._cfg["app"].get("user_name", "User")
        self.user_id   = self._cfg["app"].get("user_id", "default")
        self.model     = self._cfg["llm"].get("model", "llama-3.3-70b-versatile")
        
        # Wake word mode: "always" = require wake word each time, "session" = stay active for 15s
        self.wake_mode = self._cfg["app"].get("wake_mode", "always")
        self.session_timeout = 15  # seconds before auto-deactivate

        self.on_state_change = on_state_change or (lambda s: None)
        self.on_transcript   = on_transcript   or (lambda t: None)
        self.on_response     = on_response     or (lambda r: None)

        self.state     = "standby"
        self.activated = False
        self._busy     = False   # processing a request - ignore new audio
        self._mute_vad = False   # TTS playing - ignore mic input
        self._mute_call= False   # In a phone call - complete mute
        self._last_interaction = 0  # timestamp of last interaction

        print(f"[{self.app_name}] Starting...")
        print(f"[{self.app_name}] AI Name   : {self.ai_name}")
        print(f"[{self.app_name}] User      : {self.user_name}")
        print(f"[{self.app_name}] Wake word : '{self.wake_word}'")
        print(f"[{self.app_name}] Wake mode : {self.wake_mode}")
        print(f"[{self.app_name}] Model     : {self.model}")

        from core.tts import TTSEngine
        from core.stt import STTEngine
        from core.llm import LLMEngine
        from agents.dispatcher import AgentDispatcher
        from core.noise_vad import NoiseVAD
        from core.phone_detector import PhoneDetector

        self.tts   = TTSEngine()
        self.stt   = STTEngine()
        self.llm   = LLMEngine(self.user_id)
        self.agent = AgentDispatcher(self.tts, self.llm)
        self.vad   = NoiseVAD()
        self.vad.on_speech_start = self._on_speech_start
        self.vad.on_speech_end   = self._on_audio_ready
        
        # Phone/call detector - auto-mute during calls
        self.phone = PhoneDetector(
            on_call_started=self._on_call_started,
            on_call_ended=self._on_call_ended
        )
        
        print(f"[{self.app_name}] All systems ready.")

    def _set_state(self, state: str):
        self.state = state
        self.on_state_change(state)
    
    def _on_call_started(self):
        """Called when a phone/video call is detected - completely mute AI."""
        self._mute_call = True
        self.activated = False
        self._set_state("standby")
        print(f"[{self.app_name}] Call detected - auto-muted")
    
    def _on_call_ended(self):
        """Called when call ends - resume normal operation."""
        self._mute_call = False
        print(f"[{self.app_name}] Call ended - ready to listen")
    
    def _check_session_timeout(self):
        """Auto-deactivate after 15 seconds of silence."""
        if self.activated and self.wake_mode == "session":
            if time.time() - self._last_interaction > self.session_timeout:
                self.activated = False
                self._set_state("standby")
                print(f"[{self.app_name}] Session timeout - returning to standby")

    def _on_speech_start(self):
        # Never respond if in a call
        if self._mute_call:
            return
        if self.activated and not self._mute_vad and not self._busy:
            self._set_state("listening")

    def _on_audio_ready(self, wav_bytes: bytes):
        # CRITICAL: Drop ALL audio if in a call or busy
        if self._mute_call or self._mute_vad or self._busy:
            return
        
        # Check session timeout
        self._check_session_timeout()

        self._set_state("thinking")

        try:
            text, lang = self.stt.transcribe(wav_bytes)
        except Exception as e:
            print(f"[STT] Error: {e}")
            self._set_state("standby" if not self.activated else "listening")
            return

        text = text.strip()
        if not text or len(text) < 2:
            self._set_state("standby" if not self.activated else "listening")
            return

        text_lower = text.lower()
        print(f"[STT] '{text}'")

        # Check for wake word in the utterance
        wake_detected = self._contains_wake_word(text_lower)
        
        # ALWAYS require wake word mode (like Alexa/Siri/Google)
        if self.wake_mode == "always":
            if not wake_detected:
                # No wake word = ignore completely (not talking to us)
                self._set_state("standby")
                return
            # Remove wake word from command
            text, text_lower = self._strip_wake_word(text, text_lower)
            self._last_interaction = time.time()
            
            # If only wake word was said, greet
            if not text.strip() or len(text.strip()) < 2:
                self.activated = True
                self._set_state("listening")
                msg = f"Yes sir, how can I help you?"
                self.on_response(msg)
                self._speak_blocking(msg, lang)
                return
            
            # Wake word + command in same utterance - process it
            self.activated = True
        
        # Session mode (stays active for 15s after wake word)
        elif self.wake_mode == "session":
            if not self.activated:
                if not wake_detected:
                    self._set_state("standby")
                    return
                # Activate session
                self.activated = True
                self._last_interaction = time.time()
                text, text_lower = self._strip_wake_word(text, text_lower)
                
                if not text.strip() or len(text.strip()) < 2:
                    self._set_state("listening")
                    msg = f"Yes sir, how can I help you?"
                    self.on_response(msg)
                    self._speak_blocking(msg, lang)
                    return
            else:
                self._last_interaction = time.time()
                # If wake word said again, strip it
                if wake_detected:
                    text, text_lower = self._strip_wake_word(text, text_lower)

        # Rating
        if any(w in text_lower for w in ["good response", "correct", "well done"]):
            self.llm.rate_last(1.0)
            self._speak_blocking("Good response logged.", lang)
            self._set_state("listening")
            return
        if any(w in text_lower for w in ["bad response", "wrong answer", "that was wrong"]):
            self.llm.rate_last(0.0)
            self._speak_blocking("Got it, will improve.", lang)
            self._set_state("listening")
            return

        # Sleep
        if any(w in text_lower for w in ["goodbye", "go to sleep", "sleep now", "stop listening", "deactivate", "be quiet", "silent mode", "standby"]):
            self.activated = False
            self._speak_blocking(f"Going to standby. Say {self.wake_word} to wake me.", lang)
            self._set_state("standby")
            return

        # Normal request - lock busy
        self._busy = True
        self.on_transcript(text)

        def handle():
            try:
                self._process(text, text_lower, lang)
            except Exception as e:
                print(f"[Orchestrator] Error: {e}")
                self._speak_blocking("I had an error. Please try again.", lang)
            finally:
                self._busy = False
                self._mute_vad = False
                self._set_state("listening")

        threading.Thread(target=handle, daemon=True).start()

    def _process(self, text: str, text_lower: str, lang: str):
        # 1. Try fast route first (no LLM needed, instant)
        fast = try_fast_route(text)
        if fast:
            action = fast.get("action", "")
            if action == "__sleep__":
                self.activated = False
                self._speak_blocking(f"Going to standby.", lang)
                self._set_state("standby")
                return
            print(f"[FastRoute] {action}")
            result = self.agent.dispatch(fast, lang)
            if result:
                return

        # 2. Analyze file intent (fast pattern match)
        analyze_triggers = ["analyze", "read", "understand", "review", "check"]
        file_triggers    = [".py", ".go", ".js", ".java", ".txt", ".cs", ".ts", "file", "code"]
        if any(a in text_lower for a in analyze_triggers) and any(f in text_lower for f in file_triggers):
            self._analyze_file(text, lang)
            return

        # 3. LLM intent extraction (slower path, only when needed)
        self._set_state("thinking")
        try:
            intent = self.llm.extract_intent(text)
            action = intent.get("action", "answer_question")
            print(f"[LLM Intent] {action}")
        except Exception as e:
            print(f"[LLM] Intent error: {e}")
            intent = {"action": "answer_question", "params": {}}
            action = "answer_question"

        if action != "answer_question":
            result = self.agent.dispatch(intent, lang)
            if result:
                return

        # 4. Conversational reply - streaming
        self._set_state("speaking")
        self.on_response("...")
        self._mute_vad = True

        full   = ""
        buffer = ""
        enders = (".", "!", "?", "\n")

        try:
            for token in self.llm.chat_stream(text, language=lang):
                full   += token
                buffer += token
                if buffer.rstrip().endswith(enders):
                    s = buffer.strip()
                    if s:
                        self.tts.speak(s, lang)
                    buffer = ""
            if buffer.strip():
                self.tts.speak(buffer.strip(), lang)
            self.on_response(full)
        except Exception as e:
            print(f"[LLM] Stream error: {e}")
            self.tts.speak("I had a problem. Try again.", lang)

        # Wait for TTS to drain
        for _ in range(120):
            if not self.tts.is_speaking:
                break
            time.sleep(0.1)

    def _analyze_file(self, text: str, lang: str):
        import re, os
        # Try to extract a file path from the text
        path_match = re.search(r'[A-Za-z]:[\\\/][^\s"\']+|[\\\/][^\s"\']+\.[a-z]+|[\w\\\/]+\.[a-z]{2,4}', text)
        if path_match:
            path = path_match.group()
        else:
            self._speak_blocking("Please tell me the full file path you want me to analyze.", lang)
            return

        from pathlib import Path
        p = Path(path)
        if not p.exists():
            self._speak_blocking(f"I cannot find {path}. Check the path and try again.", lang)
            return

        self._speak_blocking("Reading the file now.", lang)
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            prompt  = (f"Analyze this code and suggest improvements in 3 sentences max. "
                       f"No markdown, no lists, plain text only.\n\n{content[:3000]}")
            self._set_state("thinking")
            self._mute_vad = True
            full = ""
            for token in self.llm.chat_stream(prompt, language=lang):
                full += token
            if full.strip():
                self.tts.speak(full.strip(), lang)
                self.on_response(full)
        except Exception as e:
            self._speak_blocking(f"Could not read the file: {str(e)[:60]}", lang)

    def _speak_blocking(self, text: str, lang: str = "en"):
        self._mute_vad = True
        self.tts.speak(text, lang)
        for _ in range(100):
            if not self.tts.is_speaking:
                break
            time.sleep(0.1)
        self._mute_vad = False

    def _fuzzy(self, word: str, target: str) -> bool:
        if word == target:
            return True
        if len(word) < 3 or len(target) < 3:
            return False
        matches = sum(1 for a, b in zip(word, target) if a == b)
        return matches >= len(target) * 0.65
    
    def _contains_wake_word(self, text_lower: str) -> bool:
        """Check if text contains the wake word (exact or fuzzy)."""
        wake_parts = self.wake_word.split()
        
        # Exact match
        if self.wake_word in text_lower:
            return True
        
        # All parts present (for multi-word wake words)
        if len(wake_parts) > 1 and all(p in text_lower for p in wake_parts):
            return True
        
        # Fuzzy match (handles AI name misheard as similar words)
        words = text_lower.split()
        for word in words:
            if len(word) >= 3:
                if self._fuzzy(word, self.wake_word):
                    return True
                # Common misheard variations
                for variant in self._get_wake_variants():
                    if word == variant or self._fuzzy(word, variant):
                        return True
        return False
    
    def _get_wake_variants(self) -> list:
        """Get common misheard variations of the wake word."""
        base = self.wake_word
        variants = [base]
        # Common speech-to-text errors for popular AI names
        common_variants = {
            "astra": ["estra", "astra", "ashtray", "astro", "extra", "ash"],
            "jarvis": ["javis", "jarvice", "jarves", "jarvas", "jarv", 
                      "jervis", "service", "nervous", "jarred", "java"],
            "aria": ["arya", "area", "ariya", "ria", "arria"],
            "alexa": ["alexia", "alex", "elexia"],
            "nova": ["nava", "no va", "novah", "novella"],
            "friday": ["freya", "fry day", "fri day"],
            "alex": ["alec", "alexis", "allec"],
        }
        if base in common_variants:
            variants += common_variants[base]
        return variants
    
    def _strip_wake_word(self, text: str, text_lower: str) -> tuple:
        """Remove wake word from the beginning/middle of text."""
        # Try exact removal first
        for pattern in [f"{self.wake_word} ", f"{self.wake_word}, ", 
                        f"{self.wake_word}. ", f"hey {self.wake_word} ",
                        f"ok {self.wake_word} ", f"okay {self.wake_word} "]:
            if text_lower.startswith(pattern):
                text = text[len(pattern):]
                text_lower = text_lower[len(pattern):]
                break
        
        # Remove from middle if present
        import re
        for variant in [self.wake_word] + self._get_wake_variants():
            pattern = rf'\b{re.escape(variant)}\b[,.]?\s*'
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
            text_lower = re.sub(pattern, '', text_lower, flags=re.IGNORECASE)
        
        return text.strip(), text_lower.strip()

    def start(self):
        self.vad.start()
        self.phone.start()  # Start call detection
        self._set_state("standby")
        time.sleep(1.0)
        
        # Dynamic personalized greeting
        mode_msg = "I'll respond to each command with your wake word." if self.wake_mode == "always" else "I'll stay active for 15 seconds after hearing your wake word."
        greeting = (f"Hello {self.user_name}. I am {self.ai_name}, your personal assistant. "
                    f"Say {self.wake_word} before each command. {mode_msg}")
        self.on_response(greeting)
        self._speak_blocking(greeting, "en")

    def stop(self):
        self.vad.stop()
        self.phone.stop()

    def get_stats(self) -> dict:
        return {
            "sessions":  self.llm.memory.session_count(),
            "knowledge": self.llm.memory.knowledge_count(),
            "model":     self.model,
            "state":     self.state,
            "user_id":   self.user_id,
            "user_name": self.user_name,
            "app_name":  self.app_name,
            "ai_name":   self.ai_name,
            "wake_word": self.wake_word,
        }
