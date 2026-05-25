"""
Orchestrator - reads ALL values from config.yaml fresh on every start.
Fixes:
- Wake word detection improved
- TTS echo prevention (don't listen while speaking)
- One response per utterance (not multiple)
- Proper action routing
"""
import threading
import time
from core.config_loader import load_config


class ARIAOrchestrator:
    def __init__(self, on_state_change=None, on_transcript=None, on_response=None):
        self._cfg      = load_config()
        self.app_name  = self._cfg["app"]["name"]
        self.wake_word = self._cfg["app"]["wake_word"].lower().strip()
        self.user_id   = self._cfg["app"]["user_id"]
        self.model     = self._cfg["llm"]["model"]

        self.on_state_change = on_state_change or (lambda s: None)
        self.on_transcript   = on_transcript   or (lambda t: None)
        self.on_response     = on_response     or (lambda r: None)

        self.state     = "standby"
        self.activated = False
        self._busy     = False   # True while processing - prevents double responses
        self._mute_vad = False   # True while TTS playing - prevents hearing own voice

        print(f"[{self.app_name}] Starting...")
        print(f"[{self.app_name}] Wake word : '{self.wake_word}'")
        print(f"[{self.app_name}] Model     : {self.model}")
        print(f"[{self.app_name}] User      : {self.user_id}")

        from core.tts import TTSEngine
        from core.stt import STTEngine
        from core.llm import LLMEngine
        from agents.dispatcher import AgentDispatcher
        from core.noise_vad import NoiseVAD

        print(f"[{self.app_name}] Loading TTS...")
        self.tts = TTSEngine()

        print(f"[{self.app_name}] Loading STT...")
        self.stt = STTEngine()

        print(f"[{self.app_name}] Loading LLM...")
        self.llm = LLMEngine(self.user_id)

        print(f"[{self.app_name}] Loading agents...")
        self.agent = AgentDispatcher(self.tts, self.llm)

        print(f"[{self.app_name}] Loading VAD...")
        self.vad = NoiseVAD()
        self.vad.on_speech_start = self._on_speech_start
        self.vad.on_speech_end   = self._on_audio_ready

        print(f"[{self.app_name}] All systems ready.")

    def _set_state(self, state: str):
        self.state = state
        self.on_state_change(state)

    def _on_speech_start(self):
        # Don't light up UI while muted (TTS playing)
        if self.activated and not self._mute_vad:
            self._set_state("listening")

    def _on_audio_ready(self, wav_bytes: bytes):
        # CRITICAL: Ignore audio while TTS is playing (prevents hearing own voice)
        if self._mute_vad:
            return
        # Ignore if already processing a request
        if self._busy:
            return

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
        print(f"[STT] Heard: '{text}'")

        # --- Wake word check ---
        if not self.activated:
            wake_parts = self.wake_word.split()
            # Check if wake word (or close match) is in text
            matched = (
                self.wake_word in text_lower or
                all(p in text_lower for p in wake_parts) or
                (len(wake_parts) == 1 and any(
                    self._fuzzy_match(w, self.wake_word)
                    for w in text_lower.split()
                ))
            )
            if matched:
                self.activated = True
                self._set_state("listening")
                greeting = f"Yes sir, how can I help you?"
                self.on_response(greeting)
                self._speak(greeting, lang)
            else:
                self._set_state("standby")
            return

        # --- Control commands ---
        if any(w in text_lower for w in ["good response", "correct", "well done", "that was right"]):
            self.llm.rate_last(1.0)
            self._speak("Good response logged.", lang)
            self._set_state("listening")
            return

        if any(w in text_lower for w in ["bad response", "wrong", "that was incorrect"]):
            self.llm.rate_last(0.0)
            self._speak("Got it, I will improve.", lang)
            self._set_state("listening")
            return

        if any(w in text_lower for w in ["goodbye", "go to sleep", "sleep now", "deactivate", "stop listening"]):
            self.activated = False
            self._speak(f"Going to standby. Say {self.wake_word} when you need me.", lang)
            self._set_state("standby")
            return

        # --- Normal request ---
        self._busy = True
        self.on_transcript(text)

        # Intent extraction
        try:
            intent = self.llm.extract_intent(text)
            action = intent.get("action", "answer_question")
            print(f"[Intent] {action} | {intent.get('params', {})}")
        except Exception as e:
            print(f"[LLM] Intent error: {e}")
            intent = {"action": "answer_question", "params": {}}
            action = "answer_question"

        # --- Agentic actions ---
        if action != "answer_question":
            try:
                result = self.agent.dispatch(intent, lang)
                if result:
                    self._busy = False
                    self._set_state("listening")
                    return
            except Exception as e:
                print(f"[Agent] Error: {e}")

        # --- LLM chat (short reply) ---
        self._set_state("speaking")
        self.on_response("...")

        def stream():
            try:
                full   = ""
                buffer = ""
                enders = (".", "!", "?", "\n")
                first_chunk = True

                for token in self.llm.chat_stream(text, language=lang):
                    full   += token
                    buffer += token

                    if first_chunk:
                        # Start muting VAD as soon as first token arrives
                        self._mute_vad = True
                        first_chunk = False

                    if buffer.rstrip().endswith(enders):
                        sentence = buffer.strip()
                        if sentence:
                            self._speak_raw(sentence, lang)
                        buffer = ""

                if buffer.strip():
                    self._speak_raw(buffer.strip(), lang)

                self.on_response(full)
            except Exception as e:
                print(f"[LLM] Stream error: {e}")
                self._speak("I had an error. Please try again.", lang)
            finally:
                # Wait for TTS to finish then unmute
                for _ in range(120):
                    if not self.tts.is_speaking:
                        break
                    time.sleep(0.1)
                self._mute_vad = False
                self._busy     = False
                self._set_state("listening")

        threading.Thread(target=stream, daemon=True).start()

    def _speak(self, text: str, lang: str = "en"):
        """Speak and mute VAD during playback."""
        self._mute_vad = True
        self.tts.speak(text, lang)
        # Wait for TTS queue to empty
        for _ in range(100):
            if not self.tts.is_speaking:
                break
            time.sleep(0.1)
        self._mute_vad = False

    def _speak_raw(self, text: str, lang: str = "en"):
        """Queue without waiting (for streaming)."""
        self.tts.speak(text, lang)

    def _fuzzy_match(self, word: str, target: str) -> bool:
        """Simple fuzzy match for Indian English pronunciation variations."""
        if word == target:
            return True
        if len(word) < 3 or len(target) < 3:
            return False
        # Check if enough chars match
        matches = sum(1 for a, b in zip(word, target) if a == b)
        return matches >= len(target) * 0.7

    def start(self):
        self.vad.start()
        self._set_state("standby")
        print(f"[{self.app_name}] Speaking greeting...")
        time.sleep(1.0)  # Let audio system settle
        greeting = (
            f"Hello Sir. {self.app_name} online and ready. "
            f"Say {self.wake_word} to activate."
        )
        self.on_response(greeting)
        self._speak(greeting, "en")

    def stop(self):
        self.vad.stop()

    def get_stats(self) -> dict:
        return {
            "sessions":  self.llm.memory.session_count(),
            "knowledge": self.llm.memory.knowledge_count(),
            "model":     self.model,
            "state":     self.state,
            "user":      self.user_id,
            "name":      self.app_name,
            "wake_word": self.wake_word,
        }
