# -*- coding: utf-8 -*-
"""
Record a short clip from the microphone and print Vosk transcription.
Use this to test mic + Vosk accuracy (e.g. say "what time is it" and see if it transcribes correctly).
Run: python tools/record_and_transcribe.py [seconds]
"""

import os
import sys
import json
import argparse

_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _here)

import numpy as np
import sounddevice as sd
import config.settings as settings

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False


def get_model_path():
    pref = getattr(settings, "VOSK_MODEL_PREFERENCE", "auto").strip().lower()
    large = os.path.join(settings.MODELS_DIR, "vosk-model-en-us-0.22")
    small = os.path.join(settings.MODELS_DIR, "vosk-model-small-en-us-0.15")
    if pref == "large" and os.path.isdir(large):
        return large
    if pref == "small" and os.path.isdir(small):
        return small
    if os.path.isdir(large):
        return large
    if os.path.isdir(small):
        return small
    return None


def main():
    parser = argparse.ArgumentParser(description="Record from mic and transcribe with Vosk")
    parser.add_argument("seconds", nargs="?", type=float, default=5.0, help="Recording length in seconds (default 5)")
    args = parser.parse_args()
    duration = max(1.0, min(30.0, args.seconds))
    sample_rate = getattr(settings, "SAMPLE_RATE", 16000)

    if not VOSK_AVAILABLE:
        print("Vosk not installed. pip install vosk")
        return 1
    path = get_model_path()
    if not path:
        print("No Vosk model found in", settings.MODELS_DIR)
        print("Download e.g. vosk-model-small-en-us-0.15 and extract there.")
        return 1

    print("Loading model:", path)
    model = Model(path)
    rec = KaldiRecognizer(model, sample_rate)
    print("Recording for %.1f seconds... Speak now." % duration)
    try:
        data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()
    except Exception as e:
        print("Recording failed:", e)
        return 1

    # Feed in chunks (same as voice_pipeline)
    chunk_sec = getattr(settings, "VOSK_CHUNK_SEC", 0.5)
    chunk_len = int(sample_rate * 2 * chunk_sec)
    raw = data.tobytes()
    for i in range(0, len(raw), chunk_len):
        chunk = raw[i : i + chunk_len]
        if len(chunk) < chunk_len:
            break
        rec.AcceptWaveform(chunk)
    rec.AcceptWaveform(b"")  # flush
    result = json.loads(rec.FinalResult())
    text = (result.get("text") or "").strip()
    print("Transcription:", repr(text) if text else "(empty)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
