"""
STT - faster-whisper
Uses base.en on CPU for Indian English accuracy.
tiny.en is too inaccurate for Indian accents.
"""
import os
import tempfile
from core.config_loader import load_config


def _detect_device():
    try:
        import ctypes
        ctypes.cdll.LoadLibrary("cublas64_12.dll")
        return "cuda", "int8"
    except Exception:
        pass
    return "cpu", "int8"


class STTEngine:
    def __init__(self):
        _cfg   = load_config()
        self.lang = _cfg["voice"]["language"]
        device, compute = _detect_device()

        # Use base.en on CPU - much better for Indian English than tiny.en
        # tiny.en mishears "Jarvis" as "Job is", "service" etc.
        if device == "cuda":
            model_name = _cfg["voice"]["stt_model"]
            print(f"[STT] CUDA found - using {model_name}")
        else:
            model_name = "base.en"
            print("[STT] CPU mode - using base.en (better Indian English accuracy)")

        from faster_whisper import WhisperModel
        print(f"[STT] Loading {model_name} ...")
        self.model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute,
            cpu_threads=4,
            num_workers=1,
        )
        print("[STT] Ready")

    def transcribe(self, wav_bytes: bytes) -> tuple:
        """Returns (text, detected_language)"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        try:
            lang = None if self.lang == "auto" else self.lang
            segments, info = self.model.transcribe(
                tmp_path,
                beam_size=5,
                language=lang,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                temperature=0.0,
                condition_on_previous_text=False,
            )
            parts = [s.text.strip() for s in segments]
            text  = " ".join(parts).strip()
            return text, info.language
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
