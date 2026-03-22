# -*- coding: utf-8 -*-
"""Voice pipeline: mic capture, VAD, STT (local), TTS (human-like: Edge TTS, fallback pyttsx3)."""

import os
import sys
import queue
import threading
import tempfile
import asyncio
import numpy as np
import sounddevice as sd
import config.settings as settings

# Optional: Vosk for offline STT
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

# Optional: faster-whisper for more accurate STT (local)
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# Optional: Edge TTS for human-like speech (natural voice)
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

# Optional: pyttsx3 for TTS fallback
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

# Optional: webrtcvad for VAD
try:
    import webrtcvad
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False


def _get_vosk_model_path() -> str | None:
    pref = getattr(settings, "VOSK_MODEL_PREFERENCE", "auto").strip().lower()
    large_path = os.path.join(settings.MODELS_DIR, "vosk-model-en-us-0.22")
    small_path = os.path.join(settings.MODELS_DIR, "vosk-model-small-en-us-0.15")
    # Always fall back to small if preferred model missing (so voice always works)
    if pref == "large":
        return large_path if os.path.isdir(large_path) else (small_path if os.path.isdir(small_path) else None)
    if pref == "small":
        return small_path if os.path.isdir(small_path) else None
    # "auto": prefer larger model for better accuracy
    if os.path.isdir(large_path):
        return large_path
    if os.path.isdir(small_path):
        return small_path
    return None


def _log_stt(msg: str) -> None:
    try:
        log_path = os.path.join(settings.DATA_DIR, "startup_log.txt")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


class VoicePipeline:
    """Captures mic, runs VAD, STT (Whisper or Vosk), and TTS. Owner check is done externally."""

    def __init__(self, on_transcript=None, on_speak=None):
        self.sample_rate = settings.SAMPLE_RATE
        # on_transcript(text: str, audio: np.ndarray | None) — audio is the buffer that produced text (for owner verify)
        self.on_transcript = on_transcript
        self.on_speak = on_speak
        self._vad = webrtcvad.Vad(settings.VAD_AGGRESSIVENESS) if WEBRTC_AVAILABLE else None
        self._vosk_model = None
        self._vosk_recognizer = None
        self._whisper_model = None
        self._stt_backend = None  # "whisper" or "vosk"
        self._tts_engine = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._running = False
        self._stream = None
        self._stt_thread = None
        self._init_stt()
        self._init_tts()

    def _init_stt(self) -> None:
        backend = getattr(settings, "STT_BACKEND", "vosk").strip().lower()
        # Prefer Whisper when requested and available (more accurate)
        if backend == "whisper":
            if not WHISPER_AVAILABLE:
                _log_stt("Whisper not installed (pip install faster-whisper). Using Vosk.")
            else:
                try:
                    model_name = getattr(settings, "WHISPER_MODEL", "base.en")
                    device = getattr(settings, "WHISPER_DEVICE", "cpu")
                    compute_type = getattr(settings, "WHISPER_COMPUTE_TYPE", "int8")
                    self._whisper_model = WhisperModel(model_name, device=device, compute_type=compute_type)
                    self._stt_backend = "whisper"
                    _log_stt("STT backend: whisper (%s)" % model_name)
                    return
                except Exception as e:
                    _log_stt("Whisper init failed: %s" % e)
                    self._whisper_model = None
        # Fallback to Vosk
        if not VOSK_AVAILABLE:
            return
        path = _get_vosk_model_path()
        if not path:
            return
        try:
            self._vosk_model = Model(path)
            self._vosk_recognizer = KaldiRecognizer(self._vosk_model, self.sample_rate)
            self._stt_backend = "vosk"
            _log_stt("STT backend: vosk")
        except Exception as e:
            _log_stt("STT init failed: %s" % e)
            self._vosk_model = None
            self._vosk_recognizer = None

    def _init_tts(self) -> None:
        self._edge_voice = getattr(settings, "EDGE_TTS_VOICE", "en-US-JennyNeural")
        if PYTTSX3_AVAILABLE:
            try:
                self._tts_engine = pyttsx3.init()
                self._tts_engine.setProperty("rate", 150)
                self._tts_engine.setProperty("volume", 1.0)
            except Exception:
                pass

    def _speak_edge_tts(self, text: str) -> bool:
        """Speak with Edge TTS (human-like). Returns True if used."""
        if not EDGE_TTS_AVAILABLE or not text.strip():
            return False
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name
            async def _gen():
                communicate = edge_tts.Communicate(text, self._edge_voice)
                await communicate.save(tmp_path)
            asyncio.run(_gen())
            try:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    import time
                    time.sleep(0.1)
            except Exception:
                try:
                    os.startfile(tmp_path)
                    import time
                    time.sleep(max(1, len(text) * 0.05))
                except Exception:
                    pass
            return True
        except Exception:
            return False
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def start_listening(self) -> None:
        """Start recording and STT processing."""
        if self._running:
            return
        self._running = True
        self._audio_queue = queue.Queue()
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=int(self.sample_rate * settings.FRAME_MS / 1000),
            callback=self._audio_callback,
        )
        self._stream.start()
        self._stt_thread = threading.Thread(target=self._process_audio, daemon=True)
        self._stt_thread.start()

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            pass  # log if needed
        try:
            # indata can be cffi buffer (no .copy()); get a numpy copy
            chunk = np.frombuffer(indata, dtype=np.int16).copy()
            self._audio_queue.put(chunk)
        except queue.Full:
            pass

    def _process_audio(self) -> None:
        if self._whisper_model:
            self._process_audio_whisper()
        else:
            self._process_audio_vosk()

    def _process_audio_whisper(self) -> None:
        """Accumulate audio and transcribe with Whisper every WHISPER_CHUNK_SEC."""
        chunk_sec = getattr(settings, "WHISPER_CHUNK_SEC", 2.5)
        chunk_samples = int(self.sample_rate * chunk_sec)
        chunk_bytes = chunk_samples * 2  # int16
        buffer = b""
        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.2)
                buffer += chunk.tobytes()
                if len(buffer) >= chunk_bytes and self._whisper_model and self.on_transcript:
                    audio_bytes = buffer[:chunk_bytes]
                    buffer = buffer[chunk_bytes:]
                    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
                    audio_float = audio_int16.astype(np.float32) / 32768.0
                    try:
                        segments, _ = self._whisper_model.transcribe(
                            audio_float,
                            language="en",
                            beam_size=1,
                            vad_filter=True,
                        )
                        text = " ".join((s.text or "").strip() for s in segments).strip()
                        if text:
                            min_words = getattr(settings, "MIN_COMMAND_WORDS", 1)
                            min_chars = getattr(settings, "MIN_COMMAND_CHARS", 4)
                            w = text.split()
                            if (len(w) >= min_words and len(text) >= min_chars) or len(w) >= 2:
                                self.on_transcript(text, audio_float)
                    except Exception:
                        pass
            except queue.Empty:
                continue
            except Exception:
                buffer = b""

    def _process_audio_vosk(self) -> None:
        import json
        buffer = b""
        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.2)
                buffer += chunk.tobytes()
                chunk_sec = getattr(settings, "VOSK_CHUNK_SEC", 0.5)
                chunk_len = int(self.sample_rate * 2 * chunk_sec)  # 16kHz mono, 2 bytes per sample
                if len(buffer) >= chunk_len:
                    if self._vosk_recognizer:
                        chunk_bytes = buffer[:chunk_len]
                        self._vosk_recognizer.AcceptWaveform(chunk_bytes)
                        # Final result (end of utterance) — only send if phrase is long enough (avoid "i'm", "a", "but")
                        result = self._vosk_recognizer.Result()
                        try:
                            d = json.loads(result)
                            text = (d.get("text") or "").strip()
                            if text and self.on_transcript:
                                w = text.split()
                                if len(w) >= 2 or len(text) >= 8:
                                    audio_int16 = np.frombuffer(chunk_bytes, dtype=np.int16)
                                    audio_float = audio_int16.astype(np.float32) / 32768.0
                                    self.on_transcript(text, audio_float)
                        except Exception:
                            pass
                        # Partial result (catch "open chrome", "who are you" etc.)
                        try:
                            partial = self._vosk_recognizer.PartialResult()
                            d = json.loads(partial)
                            part_text = (d.get("partial") or d.get("text") or "").strip()
                            if part_text and self.on_transcript and (len(part_text.split()) >= 2 or len(part_text) >= 8):
                                self.on_transcript(part_text, None)
                        except Exception:
                            pass
                        buffer = buffer[chunk_len:]
                    else:
                        buffer = buffer[-chunk_len:]  # keep last 0.5s
            except queue.Empty:
                continue
            except Exception:
                buffer = b""

    def stop_listening(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def speak(self, text: str) -> None:
        """Speak text: prefer Edge TTS (human-like), fallback to pyttsx3."""
        if not text:
            return
        if self.on_speak:
            self.on_speak(text)
        # Prefer human-like Edge TTS
        if self._speak_edge_tts(text):
            return
        if self._tts_engine:
            try:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            except Exception:
                pass

    def is_stt_ready(self) -> bool:
        return self._whisper_model is not None or self._vosk_recognizer is not None

    def is_tts_ready(self) -> bool:
        return EDGE_TTS_AVAILABLE or self._tts_engine is not None
