"""
Noise cancellation + Smart VAD
Waits for complete sentence before sending to STT.
Graceful fallback if pyaudio or webrtcvad fails.
"""
import threading
import time
import io
import wave
import collections
import numpy as np
from core.config_loader import load_config

SAMPLE_RATE = 16000
FRAME_MS    = 30
FRAME_SIZE  = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480 samples

class NoiseVAD:
    def __init__(self):
        _cfg = load_config()
        self.aggressiveness  = int(_cfg["voice"]["vad_aggressiveness"])
        self.silence_ms      = int(_cfg["voice"]["silence_threshold_ms"])
        self.do_noise_cancel = bool(_cfg["voice"]["noise_cancel"])
        self.on_speech_start = None
        self.on_speech_end   = None
        self.running         = False
        self._vad            = None
        self._pa             = None
        self._init_vad()

    def _init_vad(self):
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(self.aggressiveness)
            print("[VAD] webrtcvad loaded")
        except Exception as e:
            print(f"[VAD] webrtcvad not available: {e}")

        try:
            import pyaudio
            self._pa = pyaudio.PyAudio()
            print("[VAD] PyAudio loaded")
        except Exception as e:
            print(f"[VAD] PyAudio not available: {e}")

    def _noise_reduce(self, audio_np):
        try:
            import noisereduce as nr
            reduced = nr.reduce_noise(y=audio_np.astype(np.float32), sr=SAMPLE_RATE)
            return reduced.astype(np.int16)
        except Exception:
            return audio_np

    def _to_wav_bytes(self, audio_np):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_np.tobytes())
        buf.seek(0)
        return buf.read()

    def _is_speech(self, frame_bytes):
        if self._vad is None:
            return True  # If no VAD, treat everything as speech
        try:
            return self._vad.is_speech(frame_bytes, SAMPLE_RATE)
        except Exception:
            return True

    def _listen_loop(self):
        if self._pa is None:
            print("[VAD] No PyAudio - cannot listen")
            return

        import pyaudio
        silence_frames_needed = int(self.silence_ms / FRAME_MS)
        pre_buffer_frames     = int(300 / FRAME_MS)  # 300ms pre-roll
        ring = collections.deque(maxlen=pre_buffer_frames)

        try:
            stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=FRAME_SIZE,
            )
        except Exception as e:
            print(f"[VAD] Could not open microphone: {e}")
            return

        print(f"[VAD] Listening... (silence threshold: {self.silence_ms}ms)")
        in_speech     = False
        voiced_frames = []
        silence_count = 0

        while self.running:
            try:
                raw = stream.read(FRAME_SIZE, exception_on_overflow=False)
            except Exception:
                time.sleep(0.01)
                continue

            is_speech = self._is_speech(raw)

            if not in_speech:
                ring.append(raw)
                if is_speech:
                    in_speech     = True
                    voiced_frames = list(ring)
                    silence_count = 0
                    if self.on_speech_start:
                        threading.Thread(
                            target=self.on_speech_start, daemon=True
                        ).start()
            else:
                voiced_frames.append(raw)
                if not is_speech:
                    silence_count += 1
                    if silence_count >= silence_frames_needed:
                        # Sentence complete
                        all_audio = b"".join(voiced_frames)
                        audio_np  = np.frombuffer(all_audio, dtype=np.int16)
                        if self.do_noise_cancel:
                            audio_np = self._noise_reduce(audio_np)
                        wav_bytes = self._to_wav_bytes(audio_np)
                        if self.on_speech_end:
                            threading.Thread(
                                target=self.on_speech_end,
                                args=(wav_bytes,),
                                daemon=True,
                            ).start()
                        in_speech     = False
                        voiced_frames = []
                        ring.clear()
                        silence_count = 0
                else:
                    silence_count = 0

        stream.stop_stream()
        stream.close()
        print("[VAD] Stopped")

    def start(self):
        self.running = True
        t = threading.Thread(target=self._listen_loop, daemon=True)
        t.start()

    def stop(self):
        self.running = False
