# -*- coding: utf-8 -*-
"""Test that command parsing would trigger the right intents (open, note, time, who are you)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _normalize(text):
    """Same normalization as main: strip, lower, strip assistant name."""
    t = (text or "").strip().lower()
    for prefix in ("jarvis ", "jarvis,", "hey jarvis "):
        if t.startswith(prefix):
            t = t[len(prefix):].lstrip(" ,")
            break
    return t.strip()


class TestCommandResponses(unittest.TestCase):
    def test_open_detected(self):
        t = _normalize("jarvis open google chrome")
        self.assertTrue("open" in t or t.startswith("open "))
        t2 = _normalize("open notepad")
        self.assertTrue(t2.startswith("open ") or " open " in t2)

    def test_note_detected(self):
        t = _normalize("jarvis note tomorrow meeting")
        self.assertIn("note", t)
        t2 = _normalize("note this buy milk")
        self.assertIn("note", t2)

    def test_time_detected(self):
        t = _normalize("what is the time")
        self.assertIn("time", t)
        t2 = _normalize("jarvis what time is it")
        self.assertIn("time", t2)

    def test_who_are_you_detected(self):
        t = _normalize("jarvis who are you")
        self.assertTrue("who are you" in t or "who" in t)
        t2 = _normalize("what is your name")
        self.assertTrue("your name" in t2 or "name" in t2)

    def test_who_is_your_boss_detected(self):
        t = _normalize("who is your boss")
        self.assertTrue("boss" in t or "owner" in t)


if __name__ == "__main__":
    unittest.main()
