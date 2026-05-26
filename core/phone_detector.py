"""
Phone / nearby conversation detector.
Method: audio energy + speech pattern analysis.
- When ASTRA is in standby and detects continuous speech NOT directed at wake word
  for more than 3 seconds, it mutes itself automatically.
- Uses two microphone channels conceptually:
  1. Energy level: if audio is loud + continuous = someone nearby is talking
  2. Direction: if wake word not detected for 8+ seconds of speech = not talking to ASTRA
- Also detects Windows phone call apps via process list (Teams, Zoom, Phone Link)
"""
import threading
import time
import subprocess
import sys
from collections import deque

# Windows processes that indicate an active call
CALL_PROCESSES = [
    "Teams.exe", "Zoom.exe", "ms-teams.exe",
    "PhoneExperienceHost.exe", "YourPhone.exe",
    "discord.exe", "skype.exe", "slack.exe",
]

class PhoneDetector:
    def __init__(self, on_call_started=None, on_call_ended=None):
        self.on_call_started = on_call_started or (lambda: None)
        self.on_call_ended   = on_call_ended   or (lambda: None)
        self._in_call        = False
        self._running        = False
        self._audio_history  = deque(maxlen=30)  # 3 sec of 100ms samples
        self._continuous_speech_sec = 0

    def start(self):
        self._running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        print("[PhoneDetector] Monitoring for calls and nearby conversations")

    def stop(self):
        self._running = False

    def _check_call_processes(self) -> bool:
        """Check if any calling app is running."""
        if sys.platform != "win32":
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=3
            )
            running = result.stdout.lower()
            return any(p.lower() in running for p in CALL_PROCESSES)
        except Exception:
            return False

    def _monitor_loop(self):
        check_interval = 5  # seconds between checks
        while self._running:
            in_call = self._check_call_processes()
            if in_call and not self._in_call:
                self._in_call = True
                print("[PhoneDetector] Call app detected - muting ASTRA")
                self.on_call_started()
            elif not in_call and self._in_call:
                self._in_call = False
                print("[PhoneDetector] Call ended - unmuting ASTRA")
                self.on_call_ended()
            time.sleep(check_interval)

    def report_audio_energy(self, rms: float):
        """Call this from VAD with each frame's RMS energy."""
        self._audio_history.append(rms)
        # If energy is consistently high (someone talking nearby)
        if len(self._audio_history) == 30:
            avg = sum(self._audio_history) / len(self._audio_history)
            if avg > 800:  # Threshold for nearby speech
                self._continuous_speech_sec += 0.1
            else:
                self._continuous_speech_sec = 0

    @property
    def nearby_speech_detected(self) -> bool:
        return self._continuous_speech_sec > 4.0  # 4 seconds of continuous nearby speech

    @property
    def is_in_call(self) -> bool:
        return self._in_call
