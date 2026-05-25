"""
TTS Engine - Smart fallback chain:
1. piper (local, fast, best quality)
2. gTTS (online, always works)
3. print only (if everything fails)
No crash on any platform.
"""
import subprocess
import threading
import queue
import os
import sys
import time
import tempfile
from pathlib import Path
from core.config_loader import load_config

_cfg = load_config()
BASE       = Path(__file__).resolve().parent.parent
FILLER_WAV = BASE / "assets" / "hmm.wav"
VOICES_DIR = BASE / "assets" / "voices"


def _find_piper():
    """Find piper binary: scripts folder, venv, PATH, or beside main.py"""
    candidates = [
        BASE / "piper" / "piper.exe",
        BASE / "piper.exe",
        Path(sys.executable).parent / "piper.exe",
        Path(sys.executable).parent / "Scripts" / "piper.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # Try PATH
    try:
        result = subprocess.run(
            ["where", "piper"] if sys.platform == "win32" else ["which", "piper"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    return None


def _pygame_init():
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=1024)
        return pygame
    except Exception as e:
        print(f"[TTS] pygame init failed: {e}")
        return None


class TTSEngine:
    def __init__(self):
        _c = load_config()
        self.piper_voice   = _c["tts"]["piper_voice"]
        self.length_scale  = float(_c["tts"]["piper_length_scale"])
        self.use_filler    = bool(_c["tts"]["filler_sounds"])
        self._speaking     = False
        self._q            = queue.Queue()
        self._piper_bin    = _find_piper()
        self._pygame       = _pygame_init()

        if self._piper_bin:
            print(f"[TTS] Piper found: {self._piper_bin}")
        else:
            print("[TTS] Piper not found - will use gTTS (needs internet)")

        # Start background worker
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
        print("[TTS] Ready")

    def _worker(self):
        while True:
            item = self._q.get()
            if item is None:
                self._q.task_done()
                continue
            text, lang = item
            self._speaking = True
            try:
                self._say(text, lang)
            except Exception as e:
                print(f"[TTS] Worker error: {e}")
            self._speaking = False
            self._q.task_done()

    def speak(self, text: str, language: str = "en"):
        text = text.strip()
        if not text:
            return
        print(f"[TTS] Queued: {text[:60]}")
        self._q.put((text, language))

    def play_filler(self):
        if not self.use_filler:
            return
        if FILLER_WAV.exists() and self._pygame:
            try:
                sound = self._pygame.mixer.Sound(str(FILLER_WAV))
                sound.play()
            except Exception:
                pass

    @property
    def is_speaking(self):
        return self._speaking or not self._q.empty()

    def stop(self):
        with self._q.mutex:
            self._q.queue.clear()
        if self._pygame:
            try:
                self._pygame.mixer.stop()
            except Exception:
                pass

    # ---- synthesis methods ------------------------------------------------

    def _say(self, text: str, lang: str):
        # Tamil -> gTTS directly
        if lang == "ta":
            self._gtts(text, "ta")
            return
        # Try piper first
        if self._piper_bin:
            ok = self._piper(text)
            if ok:
                return
        # Fallback to gTTS
        self._gtts(text, lang)

    def _piper(self, text: str) -> bool:
        voice_onnx = VOICES_DIR / f"{self.piper_voice}.onnx"
        if not voice_onnx.exists():
            print(f"[TTS] Voice file missing: {voice_onnx}")
            return False
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            cmd = [
                self._piper_bin,
                "--model", str(voice_onnx),
                "--output_file", tmp.name,
                "--length-scale", str(self.length_scale),
                "--sentence-silence", "0.2",
            ]
            result = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0:
                print(f"[TTS] Piper error: {result.stderr[:200]}")
                return False
            self._play_wav(tmp.name)
            return True
        except FileNotFoundError:
            print("[TTS] Piper binary not found")
            return False
        except Exception as e:
            print(f"[TTS] Piper exception: {e}")
            return False
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    def _gtts(self, text: str, lang: str = "en"):
        try:
            from gtts import gTTS
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            # Map language codes
            lang_map = {"en": "en", "ta": "ta", "hi": "hi", "auto": "en"}
            gtts_lang = lang_map.get(lang, "en")
            gTTS(text=text, lang=gtts_lang, slow=False).save(tmp.name)
            self._play_mp3(tmp.name)
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
        except Exception as e:
            print(f"[TTS] gTTS failed: {e}")
            print(f"[TTS] Would have said: {text}")

    def _play_wav(self, path: str):
        if self._pygame:
            try:
                sound = self._pygame.mixer.Sound(path)
                sound.play()
                while self._pygame.mixer.get_busy():
                    time.sleep(0.02)
                return
            except Exception as e:
                print(f"[TTS] pygame wav error: {e}")
        # Fallback: Windows winsound
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME)
            return
        except Exception:
            pass
        # Fallback: playsound
        try:
            import playsound
            playsound.playsound(path)
        except Exception as e:
            print(f"[TTS] playsound error: {e}")

    def _play_mp3(self, path: str):
        if self._pygame:
            try:
                self._pygame.mixer.music.load(path)
                self._pygame.mixer.music.play()
                while self._pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                return
            except Exception as e:
                print(f"[TTS] pygame mp3 error: {e}")
        # Fallback: os.startfile (Windows plays with default player)
        try:
            if sys.platform == "win32":
                os.startfile(path)
                time.sleep(3)  # Wait approximate duration
        except Exception as e:
            print(f"[TTS] mp3 fallback error: {e}")
