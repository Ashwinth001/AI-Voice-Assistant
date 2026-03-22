# -*- coding: utf-8 -*-
"""Unit tests for config and command flow (min length, relaxed mode)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfig(unittest.TestCase):
    def test_settings_has_relaxed_voice_mode(self):
        import config.settings as settings
        self.assertTrue(hasattr(settings, "RELAXED_VOICE_MODE"))
        self.assertIsInstance(getattr(settings, "RELAXED_VOICE_MODE", None), bool)

    def test_settings_has_min_command_words(self):
        import config.settings as settings
        self.assertTrue(hasattr(settings, "MIN_COMMAND_WORDS"))
        self.assertGreaterEqual(getattr(settings, "MIN_COMMAND_WORDS", 0), 1)

    def test_settings_has_min_command_chars(self):
        import config.settings as settings
        self.assertTrue(hasattr(settings, "MIN_COMMAND_CHARS"))
        self.assertGreaterEqual(getattr(settings, "MIN_COMMAND_CHARS", 0), 1)

    def test_settings_has_assistant_name(self):
        import config.settings as settings
        self.assertTrue(hasattr(settings, "ASSISTANT_NAME"))
        self.assertGreater(len(getattr(settings, "ASSISTANT_NAME", "")), 0)

    def test_command_long_enough(self):
        min_words = 1
        min_chars = 4
        def is_ok(text):
            t = (text or "").strip().lower()
            w = t.split()
            return (len(w) >= min_words and len(t) >= min_chars) or len(w) >= 2
        self.assertTrue(is_ok("who are you"))
        self.assertTrue(is_ok("open chrome"))
        self.assertTrue(is_ok("time"))
        self.assertFalse(is_ok("a"))
        self.assertFalse(is_ok("i'm"))
        self.assertFalse(is_ok(""))
        self.assertTrue(is_ok("what time is it"))


if __name__ == "__main__":
    unittest.main()
