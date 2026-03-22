# -*- coding: utf-8 -*-
"""
Windows AI Voice Assistant — Owner-only voice, system overlay, self-learning, local security.
Runs entirely on your machine; no external models or cloud.
"""

import sys
import os
import threading
import queue
import time
from datetime import datetime

# Add project root
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

def _log(msg: str) -> None:
    log_path = os.path.join(_here, "data", "startup_log.txt")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

_log("Starting...")

import config.settings as settings
from core.voice_owner import OwnerVoiceVerifier
from core.voice_pipeline import VoicePipeline
from core.brain import Brain
from core.llm import LocalLLM
from core.security import SecurityMonitor
from core import actions as system_actions
from ui.overlay import create_overlay_app, OverlayWindow
from ui.avatar_overlay import create_avatar_overlay, AvatarOverlayWidget
try:
    from PyQt6.QtCore import QTimer
except ImportError:
    QTimer = None
_log("Imports OK")


class Assistant:
    """Main assistant: owner-only voice, overlay UI, brain, security. Obeys owner only."""

    def __init__(self):
        _log("Creating verifier, brain, llm, security...")
        self.verifier = OwnerVoiceVerifier()
        self.brain = Brain()
        self.llm = LocalLLM()
        self.security = SecurityMonitor(on_threat=self._on_threat)
        _log("Creating overlay...")
        try:
            self.app, self.overlay = create_avatar_overlay()
            if self.overlay is None:
                self.app, self.overlay = create_overlay_app()
            _log("Overlay: app=%s overlay=%s" % (self.app is not None, self.overlay is not None))
        except Exception as e:
            _log("Overlay failed: %s" % e)
            import traceback
            _log(traceback.format_exc())
            self.app, self.overlay = None, None
        self.pipeline = VoicePipeline(
            on_transcript=self._on_transcript,
            on_speak=lambda t: self._overlay_set_line(t) if self.overlay else None,
        )
        _log("STT ready: %s" % self.pipeline.is_stt_ready())
        self._command_queue: queue.Queue = queue.Queue()
        self._last_audio_buffer: list = []
        self._enrolling = False
        self._enroll_count = 0
        self.assistant_name = getattr(settings, "ASSISTANT_NAME", "Assistant")
        # Debounce: wait for user to finish speaking before queueing (buffer latest transcript, queue after silence)
        self._transcript_buffer = ""
        self._debounce_timer = None
        self._debounce_lock = threading.Lock()

    def _overlay_set_status(self, text: str) -> None:
        if self.overlay:
            self.overlay.set_status(text)

    def _overlay_set_line(self, text: str) -> None:
        if self.overlay:
            self.overlay.set_line(text)

    def _overlay_set_line_from_thread(self, text: str) -> None:
        """Post overlay line update to main thread (safe when called from STT thread)."""
        if not self.overlay:
            return
        if self.app and QTimer is not None:
            QTimer.singleShot(0, lambda t=text: self._overlay_set_line(t))
        else:
            self._overlay_set_line(text)

    def _overlay_set_status_from_thread(self, text: str) -> None:
        """Post overlay status update to main thread (safe when called from STT thread)."""
        if not self.overlay:
            return
        if self.app and QTimer is not None:
            QTimer.singleShot(0, lambda t=text: self._overlay_set_status(t))
        else:
            self._overlay_set_status(text)

    def _overlay_set_speaking(self, speaking: bool) -> None:
        """Tell avatar overlay to animate mouth (main thread only)."""
        if self.overlay and hasattr(self.overlay, "set_speaking"):
            self.overlay.set_speaking(speaking)

    def _speak_with_mouth(self, text: str) -> None:
        """Speak and drive avatar mouth animation (safe from worker thread)."""
        if not text or not text.strip():
            return
        try:
            if self.app and QTimer is not None:
                QTimer.singleShot(0, lambda: self._overlay_set_speaking(True))
            self.pipeline.speak(text)
        except Exception:
            _log("Speak error: " + str(text)[:50])
        finally:
            if self.app and QTimer is not None:
                try:
                    QTimer.singleShot(0, lambda: self._overlay_set_speaking(False))
                except Exception:
                    pass

    def _on_threat(self, name: str, reason: str) -> None:
        self._overlay_set_status(f"Security: {reason}")
        self._overlay_set_line(name[:80])

    def _schedule_transcript(self, text: str) -> None:
        """Buffer transcript and queue only after TRANSCRIPT_DEBOUNCE_SEC of silence (so full sentence is used)."""
        if not text or not text.strip():
            return
        debounce_sec = getattr(settings, "TRANSCRIPT_DEBOUNCE_SEC", 1.2)
        text = text.strip()
        with self._debounce_lock:
            # Keep the longer of current buffer or new text (so we get the full phrase, not a fragment)
            if len(text) > len(self._transcript_buffer):
                self._transcript_buffer = text
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(debounce_sec, self._on_debounce_fired)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _on_debounce_fired(self) -> None:
        """Called after silence: queue the buffered transcript if long enough."""
        with self._debounce_lock:
            to_queue = self._transcript_buffer
            self._transcript_buffer = ""
            self._debounce_timer = None
        if not to_queue:
            return
        min_words = getattr(settings, "MIN_COMMAND_WORDS", 1)
        min_chars = getattr(settings, "MIN_COMMAND_CHARS", 4)
        words = to_queue.split()
        is_long_enough = (len(words) >= min_words and len(to_queue) >= min_chars) or len(words) >= 2
        if is_long_enough:
            self._command_queue.put(("text", to_queue))
            _log("Command (after pause): " + to_queue[:80])

    def _on_transcript(self, text: str, audio=None) -> None:
        try:
            self._on_transcript_impl(text, audio)
        except Exception:
            import traceback
            _log("_on_transcript error: " + traceback.format_exc())

    def _on_transcript_impl(self, text: str, audio=None) -> None:
        if not text or not text.strip():
            return
        if getattr(settings, "LOG_RAW_TRANSCRIPT", False):
            _log("Raw transcript: " + (text.strip()[:120]))
        # Show what we heard (so you can see if mic/STT is working) — post to main thread
        if len(text.strip()) >= 2:
            self._overlay_set_line_from_thread("Heard: " + text.strip()[:55])
        # Enrollment: collect N audio samples (any phrase), then enroll
        if self._enrolling:
            if audio is not None and len(audio) >= settings.SAMPLE_RATE // 5:  # at least 0.2s
                self._last_audio_buffer.append(audio)
                self._enroll_count = len(self._last_audio_buffer)
                self._overlay_set_status_from_thread(f"Owner voice: sample {self._enroll_count}/{settings.VOICE_PRINT_SAMPLES_NEEDED}")
                self._overlay_set_line_from_thread("Say something again" if self._enroll_count < settings.VOICE_PRINT_SAMPLES_NEEDED else "Done. Enrolled.")
                if self._enroll_count >= settings.VOICE_PRINT_SAMPLES_NEEDED:
                    self.verifier.enroll(self._last_audio_buffer, settings.SAMPLE_RATE)
                    self._enrolling = False
                    self._last_audio_buffer = []
                    self._overlay_set_line_from_thread("Owner voice saved. Only your voice will be accepted.")
            return
        # Queue commands: use relaxed mode or voice verification
        relaxed = getattr(settings, "RELAXED_VOICE_MODE", True)
        min_words = getattr(settings, "MIN_COMMAND_WORDS", 1)
        min_chars = getattr(settings, "MIN_COMMAND_CHARS", 4)
        t = text.lower().strip()
        words = t.split()
        is_long_enough = (len(words) >= min_words and len(t) >= min_chars) or len(words) >= 2
        action_keywords = (
            "open", " note ", "note ", "download", "time", "date",
            "how are you", "who are you", "what can you", "what time", "what date",
            "what is your name", "what is ur name", "who is your boss", "who is your owner", "who is ur"
        )
        if self.verifier.is_enrolled():
            if relaxed:
                if is_long_enough:
                    self._schedule_transcript(text)
                return
            if audio is not None:
                if not self.verifier.verify(audio, settings.SAMPLE_RATE):
                    self._overlay_set_line_from_thread("Voice not recognized. Only owner is accepted.")
                    return
                if is_long_enough:
                    self._schedule_transcript(text)
                return
            if is_long_enough and any(kw in t for kw in action_keywords):
                self._schedule_transcript(text)
            return
        if not self.verifier.is_enrolled():
            # No enrollment yet: accept enrollment phrase (final or partial from Vosk)
            t = text.lower().strip()
            # Exact short phrases
            if t in ("enroll", "boss enroll", "enroll me", "enroll now"):
                self.start_enrollment()
                return
            # "setup owner" / "set up owner"
            if "setup owner" in t or "set up owner" in t:
                self.start_enrollment()
                return
            # "enroll" or "boss" or "owner" in phrase
            if "enroll" in t or ("boss" in t and "owner" in t):
                self.start_enrollment()
                return
            # "I am enrolling myself as your boss or owner" and variants
            if "enrolling" in t and ("boss" in t or "owner" in t):
                self.start_enrollment()
                return
            if "i am enrolling myself" in t or "i'm enrolling myself" in t:
                self.start_enrollment()
                return
            # Config short trigger (e.g. "enroll")
            short = (getattr(settings, "ENROLL_TRIGGER_SHORT", "") or "").strip().lower()
            if short and short in t:
                self.start_enrollment()
                return
            self._overlay_set_line_from_thread("Say 'enroll' or 'boss enroll' to start.")
            return

    def _correct_stt_text(self, text: str, payload: str) -> tuple[str, str]:
        """Fix common Vosk misrecognitions so we understand every word/sentence correctly."""
        if not text:
            return text, payload
        # "god" -> "go to" (e.g. "god office" -> "go to office")
        text = text.replace(" god ", " go to ")
        if text.startswith("god "):
            text = "go to " + text[4:]
        if payload:
            payload = payload.replace(" god ", " go to ")
            if payload.strip().lower().startswith("god "):
                payload = "go to " + payload.strip()[4:].lstrip()
        # "on X" -> "open X" when X looks like an app name (e.g. "on google chrome" -> "open google chrome")
        app_hints = ("chrome", "google chrome", "notepad", "firefox", "edge", "calculator", "explorer", "paint", "cmd", "command prompt", "settings", "calc")
        if text.startswith("on ") and len(text) > 3:
            rest = text[3:].strip().lower()
            if any(h in rest for h in app_hints) or rest in app_hints:
                text = "open " + text[3:]
                if payload and len(payload) >= 3 and payload.strip().lower().startswith("on "):
                    payload = "open " + payload.strip()[3:].lstrip()
        # "not X" -> "note X" when X looks like a task/reminder (e.g. "not tomorrow I have to go to office" -> "note tomorrow...")
        note_hints = ("tomorrow", "today", "that ", "this ", "meeting", " office", " i have", " i need", " go to", "reminder", "remember")
        if text.startswith("not ") and len(text) > 4 and any(h in text for h in note_hints):
            text = "note " + text[4:]
            if payload and len(payload) >= 4 and payload.strip().lower().startswith("not "):
                payload = "note " + payload.strip()[4:].lstrip()
        return text.strip(), (payload.strip() if payload else payload)

    def _process_command(self, cmd: str, payload: str) -> None:
        if cmd != "text":
            return
        try:
            self._process_command_impl(cmd, payload)
        except Exception:
            import traceback
            _log("Command error: " + traceback.format_exc())
            self._speak_with_mouth("Sorry, I didn't catch that. Try again.")
            self._overlay_set_status(self.assistant_name)

    def _process_command_impl(self, cmd: str, payload: str) -> None:
        if cmd != "text":
            return
        text = payload.strip().lower()
        min_words = getattr(settings, "MIN_COMMAND_WORDS", 1)
        min_chars = getattr(settings, "MIN_COMMAND_CHARS", 4)
        words = text.split()
        if not ((len(words) >= min_words and len(text) >= min_chars) or len(words) >= 2):
            return
        # Normalize: remove assistant name and leading filler from anywhere
        name_lower = self.assistant_name.lower()
        for prefix in (name_lower + " ", name_lower + ",", "hey " + name_lower + " ", "okay " + name_lower + " ", "so " + name_lower + " "):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip(" ,")
                if len(payload) >= len(prefix):
                    payload = payload[len(prefix):].lstrip(" ,").strip()
                break
        if text.startswith(name_lower) and (len(text) == len(name_lower) or text[len(name_lower):len(name_lower)+1] in " ,"):
            text = text[len(name_lower):].lstrip(" ,")
            payload = payload[len(self.assistant_name):].lstrip(" ,").strip() if len(payload) >= len(self.assistant_name) else payload
        text = text.strip()
        # Correct common STT misrecognitions so we understand what the user said
        text, payload = self._correct_stt_text(text, payload)
        # --- System actions: match "open" / "note" / "download" / "search" / etc. ---
        # Open cmd/command prompt and run a command: "open cmd and run pip install X", "open cmd and write pip install X"
        if ("open cmd" in text or "open command prompt" in text) and (" and run " in text or " and write " in text):
            sep = " and run " if " and run " in text else " and write "
            if "open cmd" in text:
                rest = text.split("open cmd", 1)[-1].strip()
            else:
                rest = text.split("open command prompt", 1)[-1].strip()
            if sep in rest:
                cmd = rest.split(sep, 1)[-1].strip()
                if cmd:
                    ok, msg = system_actions.open_cmd_with_command(cmd)
                    self._speak_with_mouth(msg)
                    self.brain.store_conversation(payload, msg)
                    return
        # Standalone app/site name when user says just "YouTube", "cmd", "notepad", etc. (1–2 words)
        if len(text.split()) <= 2:
            one = text.strip().lower()
            if one in ("youtube", "gmail", "google", "chrome", "cmd", "command prompt", "notepad", "calculator", "calc", "explorer", "d drive", "drive d", "c drive", "drive c", "e drive", "drive e", "word", "winword", "microsoft word", "excel", "powerpoint"):
                ok, msg = system_actions.open_app(one)
                self._speak_with_mouth(msg)
                self.brain.store_conversation(payload, msg)
                return
        # Search X in YouTube: "search dhoom 3 in youtube", "search in youtube X"
        if " in youtube" in text or " in youtube" in payload.lower():
            if " search " in text and " in youtube" in text:
                q = text.replace(" in youtube", "").replace("search ", "").replace("search for ", "").strip()
            elif text.startswith("search ") and " in youtube" in text:
                q = text[7:].replace(" in youtube", "").strip()
            else:
                q = text.split(" in youtube")[0].strip()
                if q.startswith("search "):
                    q = q[7:].strip()
                elif q.startswith("search for "):
                    q = q[11:].strip()
            if q:
                ok, msg = system_actions.search_youtube(q)
                self._speak_with_mouth(msg)
                self.brain.store_conversation(payload, msg)
                return
        # Open D drive and open folder / open path: "open D drive and open Movies", "open D:\Videos\Movies"
        if (" open " in text or text.startswith("open ")) and (" and open " in text or "\\" in text or (" drive " in text and " open " in text)):
            if " and open " in text:
                parts = text.split(" and open ")
                if len(parts) >= 2:
                    first = parts[0].strip()
                    rest = " and open ".join(parts[1:]).strip()
                    drive_letter = None
                    if " open " in first:
                        first = first.split(" open ", 1)[-1].strip()
                    elif first.startswith("open "):
                        first = first[5:].strip()
                    if first in ("d drive", "drive d", "d"): drive_letter = "D"
                    elif first in ("c drive", "drive c", "c"): drive_letter = "C"
                    elif first in ("e drive", "drive e", "e"): drive_letter = "E"
                    if drive_letter and rest:
                        path = drive_letter + ":\\" + rest.replace(" and open ", "\\").replace(" ", "\\")
                        ok, msg = system_actions.open_path(path)
                        self._speak_with_mouth(msg)
                        self.brain.store_conversation(payload, msg)
                        return
            if "\\" in text:
                path = text.replace("open ", "").strip()
                if path:
                    ok, msg = system_actions.open_path(path)
                    self._speak_with_mouth(msg)
                    self.brain.store_conversation(payload, msg)
                    return
        # Learn a language: "learn french", "learn tamil language"
        if text.startswith("learn ") or (" learn " in text and len(text) < 50):
            lang = text.replace("learn ", "").replace(" language", "").strip()
            if lang:
                ok, msg = system_actions.open_learn_language(lang)
                self._speak_with_mouth(msg)
                self.brain.store_conversation(payload, msg)
                return
        # Speak in X from now on: "speak in tamil from now on", "let's speak in tamil"
        if "speak in " in text and ("from now on" in text or "here after" in text or "hereafter" in text or "lets speak" in text or "let's speak" in text):
            lang = text.split("speak in ")[-1].split(" from")[0].split(" here")[0].strip()
            if lang:
                self.brain.set_preference("response_language", lang)
                reply = "Got it. I'll respond in %s from now on." % lang
                self._speak_with_mouth(reply)
                self.brain.store_conversation(payload, reply)
                return
        if "lets speak in " in text or "let's speak in " in text:
            lang = text.replace("lets speak in ", "").replace("let's speak in ", "").strip()
            if lang:
                self.brain.set_preference("response_language", lang)
                reply = "Got it. I'll respond in %s from now on." % lang
                self._speak_with_mouth(reply)
                self.brain.store_conversation(payload, reply)
                return
        # "Open X and search for Y" -> open app then search
        if (" open " in text or text.startswith("open ")) and (" search for " in text or " and search for " in text):
            parts = text.replace(" and search for ", "|").replace(" search for ", "|").split("|", 1)
            if len(parts) >= 2:
                open_part = parts[0].strip()
                search_part = parts[1].strip()
                if " open " in open_part:
                    app_name = open_part.split(" open ", 1)[-1].strip()
                else:
                    app_name = open_part[5:].strip() if open_part.startswith("open ") else open_part
                if app_name.startswith("the "):
                    app_name = app_name[4:].strip()
                if app_name and search_part:
                    ok1, msg1 = system_actions.open_app(app_name)
                    self._speak_with_mouth(msg1)
                    ok2, msg2 = system_actions.open_web_search(search_part)
                    self._speak_with_mouth(msg2)
                    self.brain.store_conversation(payload, msg1 + " " + msg2)
                    return
        # Open app or site: "open chrome", "open youtube", "open microsoft word", "open winword"
        if " open " in text or text.startswith("open ") or text.endswith(" open"):
            raw = text.split(" open ", 1)[-1] if " open " in text else (text[5:] if text.startswith("open ") else text[:-5])
            app_name = raw.strip()
            if app_name.startswith("the "):
                app_name = app_name[4:].strip()
            if app_name:
                ok, msg = system_actions.open_app(app_name)
                self._speak_with_mouth(msg)
                self.brain.store_conversation(payload, msg)
                return
        # Note: "note tomorrow...", "note this buy milk", "note that meeting at 5"
        if " note " in text or text.startswith("note "):
            if " note " in text:
                after = text.split(" note ", 1)[-1].strip()
                try:
                    idx = payload.lower().index(" note ") + 6
                    content = payload[idx:].strip()
                except ValueError:
                    content = after
            else:
                after = text[5:].strip()
                content = (payload[5:].strip() if len(payload) >= 5 and payload.lower().startswith("note ") else after)
            if after.startswith("this "):
                content = (content[5:].strip() if len(content) >= 5 else content)
            elif after.startswith("that "):
                content = (content[5:].strip() if len(content) >= 5 else content)
            if content:
                ok, msg = system_actions.write_note(content)
                self._speak_with_mouth(msg)
                self.brain.store_conversation(payload, msg)
                return
            self._speak_with_mouth("What would you like me to write in the note?")
            self.brain.store_conversation(payload, "What would you like me to write in the note?")
            return
        # Download
        if "download and install" in text:
            software = text.replace("download and install", "").strip()
            if software:
                self._speak_with_mouth("Opening your browser to search for the download. You can choose 64-bit or 32-bit and run the installer when it finishes.")
                ok, msg = system_actions.open_download_search(software)
                self._speak_with_mouth(msg)
                self.brain.store_conversation(payload, msg)
                return
        if " download " in text or text.startswith("download "):
            software = (text.split(" download ", 1)[-1] if " download " in text else text[9:]).strip()
            if software:
                self._speak_with_mouth("Opening your browser to search for the download. Choose the version you need and run the installer.")
                ok, msg = system_actions.open_download_search(software)
                self._speak_with_mouth(msg)
                self.brain.store_conversation(payload, msg)
                return
        # Search the web: "search for X", "google X", "look up X", "find X"
        for trigger in ("search for ", "search ", "google ", "look up ", "find ", "look for "):
            if text.startswith(trigger) or (" " + trigger in text):
                if " search for " in text:
                    q = text.split(" search for ", 1)[-1].strip()
                elif text.startswith("search for "):
                    q = text[11:].strip()
                elif " google " in text:
                    q = text.split(" google ", 1)[-1].strip()
                elif text.startswith("google "):
                    q = text[7:].strip()
                elif " look up " in text:
                    q = text.split(" look up ", 1)[-1].strip()
                elif text.startswith("look up "):
                    q = text[8:].strip()
                elif " find " in text:
                    q = text.split(" find ", 1)[-1].strip()
                elif text.startswith("find "):
                    q = text[5:].strip()
                elif " look for " in text:
                    q = text.split(" look for ", 1)[-1].strip()
                elif text.startswith("look for "):
                    q = text[9:].strip()
                else:
                    q = text[len(trigger):].strip() if text.startswith(trigger) else text.split(trigger, 1)[-1].strip()
                if q:
                    ok, msg = system_actions.open_web_search(q)
                    self._speak_with_mouth(msg)
                    self.brain.store_conversation(payload, msg)
                    return
        # Remind me: "remind me to X", "remind me that X", "set a reminder X"
        if "remind me" in text or "set a reminder" in text or "set reminder" in text:
            if "remind me to " in text:
                content = text.split("remind me to ", 1)[-1].strip()
            elif "remind me that " in text:
                content = text.split("remind me that ", 1)[-1].strip()
            elif "set a reminder " in text:
                content = text.split("set a reminder ", 1)[-1].strip()
            elif "set reminder " in text:
                content = text.split("set reminder ", 1)[-1].strip()
            else:
                content = text.replace("remind me", "").replace("set a reminder", "").replace("set reminder", "").strip()
            if content:
                self.brain.learn_fact("reminder: " + content, "reminder")
                reply = "I'll remind you: %s. I've got it stored." % content[:60]
                self._speak_with_mouth(reply)
                self.brain.store_conversation(payload, reply)
                return
        # Simple math: "what is 15 * 23", "calculate 10 plus 5"
        if "what is " in text or "calculate " in text or "compute " in text:
            expr = None
            if "what is " in text:
                expr = text.split("what is ", 1)[-1].strip().replace(" ", "")
            elif "calculate " in text:
                expr = text.split("calculate ", 1)[-1].strip().replace(" ", "")
            elif "compute " in text:
                expr = text.split("compute ", 1)[-1].strip().replace(" ", "")
            if expr:
                expr = expr.replace("plus", "+").replace("minus", "-").replace("times", "*").replace("dividedby", "/").replace("x", "*")
                if all(c in "0123456789+-*/.()" for c in expr):
                    try:
                        result = eval(expr)
                        reply = "That's %s." % result
                        self._speak_with_mouth(reply)
                        self.brain.store_conversation(payload, reply)
                        return
                    except Exception:
                        pass
        # --- Quick answers: time, date, greeting ---
        now = datetime.now()
        if any(x in text for x in ("what the time", "whats the time", "what's the time", "what is the time", "what time is it", "current time", "time now", "tell me the time", "time please")) and not any(x in text for x in ("what the date", "whats the date", "what day")):
            time_str = now.strftime("%I:%M %p").lstrip("0")  # e.g. 2:30 PM
            reply = f"It's {time_str}. You're right on schedule."
            self._speak_with_mouth(reply)
            self.brain.store_conversation(payload, reply)
            return
        if any(x in text for x in ("what the date", "whats the date", "what's the date", "what date is it", "what day is it", "today's date", "current date")):
            date_str = now.strftime("%A, %B %d, %Y")  # e.g. Monday, February 2, 2026
            reply = f"Today is {date_str}."
            self._speak_with_mouth(reply)
            self.brain.store_conversation(payload, reply)
            return
        if any(x in text for x in ("how are you", "how do you do", "you good")):
            reply = "I'm good, thanks for asking! What can I do for you?"
            self._speak_with_mouth(reply)
            self.brain.store_conversation(payload, reply)
            return
        # Conversation: who are you, what is your name, who is your boss, what can you do
        if any(x in text for x in ("who are you", "what are you", "your name", "what is your name", "what is ur name", "whats your name", "what's your name")):
            name = self.assistant_name
            reply = f"I'm {name}, your voice assistant. I can open apps, take notes, answer questions, and just chat. What's up?"
            self._speak_with_mouth(reply)
            self.brain.store_conversation(payload, reply)
            return
        if any(x in text for x in ("who is your boss", "who is your owner", "who is ur boss", "who is ur owner", "who's your boss", "who's your owner")):
            name = self.assistant_name
            reply = f"You're my boss. I only listen to you. I'm {name}, at your service."
            self._speak_with_mouth(reply)
            self.brain.store_conversation(payload, reply)
            return
        if any(x in text for x in ("what can you do", "what do you do", "your capabilities", "what can u do")):
            reply = (
                "I can open apps and websites like Chrome, Notepad, YouTube, Gmail; search the web for anything; "
                "write notes and reminders; tell time and date; do quick math; download stuff; and chat. "
                "Just say what you want—I learn from everything you tell me."
            )
            self._speak_with_mouth(reply)
            self.brain.store_conversation(payload, reply)
            return
        # Corrections (learn from mistakes)
        if "i meant" in text or "actually" in text or "no, " in text:
            parts = text.replace("i meant", "|").replace("actually", "|").replace("no, ", "|").split("|")
            if len(parts) >= 2:
                corrected = parts[-1].strip()
                self.brain.apply_correction(parts[0].strip() or "previous", corrected, "")
                reply = "Got it. I'll remember that."
                self._speak_with_mouth(reply)
                self.brain.store_conversation(payload, reply)
                return
        # Learn fact
        if "remember" in text or "don't forget" in text or "note that" in text:
            self.brain.learn_fact(payload, "voice")
            reply = "I've remembered that."
            self._speak_with_mouth(reply)
            self.brain.store_conversation(payload, reply)
            return
        # Vocabulary / language
        if " means " in text or "translate" in text:
            parts = text.split(" means ", 1) if " means " in text else text.split("translate", 1)
            if len(parts) >= 2:
                word = parts[0].replace("translate", "").strip()
                meaning = parts[1].strip()
                self.brain.learn_vocabulary(word, meaning, "")
                reply = f"Okay, I'll remember that {word} means {meaning}."
                self._speak_with_mouth(reply)
                self.brain.store_conversation(payload, reply)
                return
        # Human-like reply from local LLM (Ollama)
        if self.llm.is_available():
            try:
                knowledge = self.brain.get_knowledge_context_for_llm(payload, limit=12)
                lang = self.brain.get_preference("response_language")
                if lang:
                    knowledge = (knowledge or "").rstrip() + "\n\nImportant: The user asked to speak in %s. Respond in %s from now on." % (lang, lang)
                recent = self.brain.get_recent_conversations(limit=8)
                reply = self.llm.chat(payload, knowledge_context=knowledge, recent_conversations=recent)
                if reply:
                    self.brain.store_conversation(payload, reply)
                    self._speak_with_mouth(reply)
                    return
            except Exception:
                pass  # fall through to brain/default
        # Fallback: retrieve from brain
        candidates = self.brain.get_response_candidates(payload)
        if candidates:
            reply = candidates[0]
            self._speak_with_mouth(reply)
            self.brain.store_conversation(payload, reply)
            return
        # Search knowledge
        results = self.brain.search_knowledge(payload, limit=1)
        if results:
            reply = results[0][0]
            self._speak_with_mouth(reply)
            self.brain.store_conversation(payload, reply)
            return
        # Reminder-like phrase without "note" prefix: "go to office", "tomorrow I have to go to office"
        reminder_words = ("tomorrow", "today", "office", "meeting", "call", "appointment")
        task_words = ("go to", "have to", "need to", "got to", "must", "remember to")
        if len(text) > 6 and any(w in text for w in reminder_words) and any(w in text for w in task_words):
            ok, msg = system_actions.write_note(payload if payload else text)
            self._speak_with_mouth(msg)
            self.brain.store_conversation(payload, msg)
            return
        # Last resort: "open X" / "note X" anywhere in phrase (e.g. "can you open chrome")
        if "open" in text:
            for app in ("chrome", "google chrome", "notepad", "calculator", "firefox", "edge", "explorer", "youtube", "word", "winword", "microsoft word", "excel", "powerpoint"):
                if app in text:
                    ok, msg = system_actions.open_app(app)
                    self._speak_with_mouth(msg)
                    self.brain.store_conversation(payload, msg)
                    return
        if "note" in text and len(text) > 10:
            try:
                idx = payload.lower().index(" note ") + 6 if " note " in payload.lower() else (payload.lower().index("note ") + 5 if payload.lower().startswith("note ") else -1)
                if idx > 0:
                    content = payload[idx:].strip()
                    if content and len(content) > 2:
                        ok, msg = system_actions.write_note(content)
                        self._speak_with_mouth(msg)
                        self.brain.store_conversation(payload, msg)
                        return
            except (ValueError, Exception):
                pass
        # LLM intent parsing: when speech was garbled, ask the model what the user wanted
        if self.llm.is_available():
            try:
                parsed = self.llm.parse_intent(payload if payload else text)
                if parsed:
                    if parsed.get("intent") == "open" and parsed.get("app"):
                        ok, msg = system_actions.open_app(parsed["app"])
                        self._speak_with_mouth(msg)
                        self.brain.store_conversation(payload, msg)
                        return
                    if parsed.get("intent") == "note" and parsed.get("content"):
                        ok, msg = system_actions.write_note(parsed["content"])
                        self._speak_with_mouth(msg)
                        self.brain.store_conversation(payload, msg)
                        return
                    if parsed.get("intent") == "time":
                        now = datetime.now()
                        time_str = now.strftime("%I:%M %p").lstrip("0")
                        reply = f"It's {time_str}. You're right on schedule."
                        self._speak_with_mouth(reply)
                        self.brain.store_conversation(payload, reply)
                        return
                    if parsed.get("intent") == "date":
                        now = datetime.now()
                        date_str = now.strftime("%A, %B %d, %Y")
                        reply = f"Today is {date_str}."
                        self._speak_with_mouth(reply)
                        self.brain.store_conversation(payload, reply)
                        return
                    if parsed.get("intent") == "search" and parsed.get("query"):
                        ok, msg = system_actions.open_web_search(parsed["query"])
                        self._speak_with_mouth(msg)
                        self.brain.store_conversation(payload, msg)
                        return
                    if parsed.get("intent") == "remind" and parsed.get("content"):
                        self.brain.learn_fact("reminder: " + parsed["content"], "reminder")
                        reply = "I'll remind you: %s. Got it stored." % parsed["content"][:60]
                        self._speak_with_mouth(reply)
                        self.brain.store_conversation(payload, reply)
                        return
                    if parsed.get("intent") == "calculate" and parsed.get("expr"):
                        try:
                            result = eval(parsed["expr"])
                            reply = "That's %s." % result
                            self._speak_with_mouth(reply)
                            self.brain.store_conversation(payload, reply)
                            return
                        except Exception:
                            pass
                    if parsed.get("intent") == "search_youtube" and parsed.get("query"):
                        ok, msg = system_actions.search_youtube(parsed["query"])
                        self._speak_with_mouth(msg)
                        self.brain.store_conversation(payload, msg)
                        return
                    if parsed.get("intent") == "open_path" and parsed.get("path"):
                        ok, msg = system_actions.open_path(parsed["path"])
                        self._speak_with_mouth(msg)
                        self.brain.store_conversation(payload, msg)
                        return
                    if parsed.get("intent") == "learn_language" and parsed.get("lang"):
                        ok, msg = system_actions.open_learn_language(parsed["lang"])
                        self._speak_with_mouth(msg)
                        self.brain.store_conversation(payload, msg)
                        return
            except Exception:
                pass
        # Default: always learn from what the user said, then respond (learn by doing everyday things)
        is_question = any(text.startswith(x) for x in ("what", "how", "when", "where", "who", "why", "can you", "could you", "is ", "are ", "do you", "does ")) or "?" in payload
        self.brain.learn_fact(payload, "voice")
        if is_question:
            reply = "I'm not sure about that one—but I've stored it and I'll learn. Want to try another way or ask something else?"
        else:
            reply = "Got it, I've remembered that. Tell me more anytime."
        self._speak_with_mouth(reply)
        self.brain.store_conversation(payload, reply)

    def _worker(self) -> None:
        while True:
            try:
                item = self._command_queue.get(timeout=0.5)
                if item is None:
                    break
                cmd, payload = item
                self._overlay_set_status("Thinking...")
                self._overlay_set_line(payload[:80])
                self._process_command(cmd, payload)
                self._overlay_set_status(self.assistant_name)
            except queue.Empty:
                continue
            except Exception:
                import traceback
                _log("Worker error: " + traceback.format_exc())
                try:
                    self._overlay_set_status(self.assistant_name)
                except Exception:
                    pass

    def start_enrollment(self) -> None:
        """Start owner voice enrollment. User says any phrase 3 times to capture voice print."""
        self._enrolling = True
        self._enroll_count = 0
        self._last_audio_buffer = []
        self._overlay_set_status("Owner voice setup")
        self._overlay_set_line("Say any phrase 3 times (e.g. 'I am the owner')")
        self._speak_with_mouth("Got it. Say any phrase three times so I can learn your voice.")

    def _speak_startup_greeting(self) -> None:
        """Speak out loud when app starts: ask for owner or greet if already enrolled."""
        name = self.assistant_name
        if not self.verifier.is_enrolled():
            self._speak_with_mouth(
                "Hi, I'm %s. Who is my owner? Say: I am enrolling myself as your boss or owner." % name
            )
        else:
            self._speak_with_mouth(
                "Hi, I'm %s. Good to see you. Say my name or just talk when you need me." % name
            )

    def run(self) -> None:
        """Run overlay and background worker. Start listening and speak startup greeting."""
        if self.overlay:
            self.overlay.show_overlay()
            if self.app:
                self.app.processEvents()
        self._overlay_set_status(self.assistant_name)
        if not self.verifier.is_enrolled():
            self._overlay_set_line("Say: I am enrolling myself as your boss or owner")
        worker = threading.Thread(target=self._worker, daemon=True)
        worker.start()
        self.security.start_monitoring()
        try:
            self.pipeline.start_listening()
            if self.verifier.is_enrolled():
                self._overlay_set_line("Listening (owner only)")
            else:
                self._overlay_set_line("Say: I am enrolling myself as your boss or owner")
            self._speak_startup_greeting()
        except Exception:
            self._overlay_set_line("Mic error - check microphone")
        if self.app:
            self.app.exec()
        else:
            _log("No PyQt - showing fallback window")
            try:
                import tkinter as tk
                root = tk.Tk()
                root.title("%s - Voice Assistant" % self.assistant_name)
                root.geometry("340x140")
                root.attributes("-topmost", True)
                tk.Label(root, text="%s running (no overlay)" % self.assistant_name, font=("Segoe UI", 10)).pack(pady=10)
                tk.Label(root, text="Say: I am enrolling myself as your boss or owner", font=("Segoe UI", 9), fg="gray").pack(pady=5)
                tk.Label(root, text="Check data\\startup_log.txt for errors.", font=("Segoe UI", 8), fg="gray").pack(pady=5)
                root.protocol("WM_DELETE_WINDOW", root.quit)
                root.mainloop()
            except Exception as e:
                _log("Fallback window failed: %s" % e)
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
        self.pipeline.stop_listening()
        self.security.stop_monitoring()
        self.brain.close()


def main() -> None:
    log_path = os.path.join(_here, "data", "startup_log.txt")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("")  # clear log for this run
        _log("Creating Assistant...")
        assistant = Assistant()
        _log("Assistant created. Running...")
        assistant.run()
        _log("App exited normally.")
    except Exception:
        import traceback
        _log("ERROR:\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
