# -*- coding: utf-8 -*-
"""Test transcript-to-intent: raw (or misrecognized) voice text maps to correct command.
   Ensures e.g. 'what time is it' -> time intent, 'open google chrome' -> open app; also
   documents that misrecognitions like 'models blah' do NOT match time (so we capture correctly)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ASSISTANT_NAME = "Jarvis"


def normalize(text, payload=None):
    """Same normalization as main: strip, lower, strip assistant name. payload defaults to text."""
    if payload is None:
        payload = text
    t = (text or "").strip().lower()
    p = (payload or "").strip()
    name_lower = ASSISTANT_NAME.lower()
    for prefix in (
        name_lower + " ",
        name_lower + ",",
        "hey " + name_lower + " ",
        "okay " + name_lower + " ",
        "so " + name_lower + " ",
    ):
        if t.startswith(prefix):
            t = t[len(prefix) :].lstrip(" ,")
            if len(p) >= len(prefix):
                p = p[len(prefix) :].lstrip(" ,").strip()
            break
    if t.startswith(name_lower) and (
        len(t) == len(name_lower) or (len(t) > len(name_lower) and t[len(name_lower) : len(name_lower) + 1] in " ,")
    ):
        t = t[len(name_lower) :].lstrip(" ,")
        if len(p) >= len(ASSISTANT_NAME):
            p = p[len(ASSISTANT_NAME) :].lstrip(" ,").strip()
    return t.strip(), p.strip()


def intent_open_app(text):
    """Return (True, app_name) if text is an 'open X' command, else (False, None). Mirrors main."""
    if " open " in text or text.startswith("open ") or text.endswith(" open"):
        raw = (
            text.split(" open ", 1)[-1]
            if " open " in text
            else (text[5:] if text.startswith("open ") else text[:-5])
        )
        app_name = raw.strip()
        if app_name.startswith("the "):
            app_name = app_name[4:].strip()
        if app_name:
            return True, app_name
    return False, None


def intent_note(text):
    """Return (True, content) if text is a 'note X' command, else (False, None). Mirrors main."""
    if " note " in text or text.startswith("note "):
        if " note " in text:
            after = text.split(" note ", 1)[-1].strip()
        else:
            after = text[5:].strip()
        if after.startswith("this "):
            after = after[5:].strip() if len(after) >= 5 else after
        elif after.startswith("that "):
            after = after[5:].strip() if len(after) >= 5 else after
        if after:
            return True, after
    return False, None


def is_time_intent(text):
    """True if text asks for the time (same phrases as main)."""
    time_phrases = (
        "what the time",
        "whats the time",
        "what's the time",
        "what is the time",
        "what time is it",
        "current time",
        "time now",
        "tell me the time",
        "time please",
    )
    date_phrases = ("what the date", "whats the date", "what day")
    if not any(x in text for x in time_phrases):
        return False
    if any(x in text for x in date_phrases):
        return False
    return True


def is_who_are_you_intent(text):
    """True if text asks who are you / your name (same as main)."""
    return any(
        x in text
        for x in (
            "who are you",
            "what are you",
            "your name",
            "what is your name",
            "what is ur name",
            "whats your name",
            "what's your name",
        )
    )


class TestTranscriptToIntent(unittest.TestCase):
    """Transcript (including possible Vosk misrecognitions) -> correct intent."""

    def test_normalize_strips_assistant_name(self):
        t, _ = normalize("Jarvis open google chrome")
        self.assertEqual(t, "open google chrome")
        t, _ = normalize("jarvis what time is it")
        self.assertEqual(t, "what time is it")

    def test_open_google_chrome_captured(self):
        t, _ = normalize("open google chrome")
        ok, app = intent_open_app(t)
        self.assertTrue(ok, "open google chrome should be open intent")
        self.assertEqual(app, "google chrome")

    def test_jarvis_open_notepad_captured(self):
        t, _ = normalize("Jarvis open notepad")
        ok, app = intent_open_app(t)
        self.assertTrue(ok)
        self.assertEqual(app, "notepad")

    def test_open_the_google_chrome_strips_the(self):
        t, _ = normalize("open the google chrome")
        ok, app = intent_open_app(t)
        self.assertTrue(ok)
        self.assertEqual(app, "google chrome")

    def test_time_intent_captured(self):
        for phrase in ("what time is it", "what's the time", "whats the time", "what is the time"):
            t, _ = normalize(phrase)
            self.assertTrue(is_time_intent(t), f"'{phrase}' should be time intent")

    def test_misrecognition_models_blah_not_time(self):
        """Vosk sometimes hears 'what time is it' as 'models blah' — must NOT match time."""
        t, _ = normalize("models blah")
        self.assertFalse(is_time_intent(t), "models blah should not be time intent")

    def test_misrecognition_random_words_not_time(self):
        t, _ = normalize("something else entirely")
        self.assertFalse(is_time_intent(t))

    def test_note_intent_captured(self):
        t, _ = normalize("note tomorrow I have to go to class")
        ok, content = intent_note(t)
        self.assertTrue(ok)
        self.assertIn("tomorrow", content)

    def test_note_this_buy_milk(self):
        t, _ = normalize("note this buy milk")
        ok, content = intent_note(t)
        self.assertTrue(ok)
        self.assertIn("buy milk", content)

    def test_who_are_you_captured(self):
        for phrase in ("who are you", "what is your name", "jarvis who are you"):
            t, _ = normalize(phrase)
            self.assertTrue(is_who_are_you_intent(t), f"'{phrase}' should be who-are-you intent")

    def test_stt_correction_on_to_open(self):
        """'on google chrome' (misheard) should be treated as open intent after correction."""
        t = "on google chrome".strip().lower()
        t = t.replace(" god ", " go to ")
        if t.startswith("on ") and any(h in t for h in ("chrome", "google chrome", "notepad")):
            t = "open " + t[3:]
        ok, app = intent_open_app(t)
        self.assertTrue(ok, "after correction 'on google chrome' -> open google chrome")
        self.assertIn("chrome", app)

    def test_stt_correction_god_to_go_to(self):
        """'god office' (misheard) should become 'go to office' for reminder-like handling."""
        t = "god office"
        t = t.replace(" god ", " go to ")
        if t.startswith("god "):
            t = "go to " + t[4:]
        self.assertIn("go to", t)
        self.assertIn("office", t)

    def test_stt_correction_not_to_note(self):
        """'not tomorrow I have to go to office' (misheard) should be treated as note."""
        t = "not tomorrow I have to go to office"
        if t.startswith("not ") and any(h in t for h in ("tomorrow", "office", " go to")):
            t = "note " + t[4:]
        ok, content = intent_note(t)
        self.assertTrue(ok)
        self.assertIn("tomorrow", content)


if __name__ == "__main__":
    unittest.main()
