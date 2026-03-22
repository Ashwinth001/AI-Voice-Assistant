# -*- coding: utf-8 -*-
"""Unit tests for core.actions (open app, write note, download search)."""

import os
import sys
import unittest

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestActions(unittest.TestCase):
    """Test system actions: open_app, write_note, open_download_search."""

    def test_open_app_notepad_returns_tuple(self):
        from core import actions
        ok, msg = actions.open_app("notepad")
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 0)

    def test_open_app_google_chrome_returns_tuple(self):
        from core import actions
        ok, msg = actions.open_app("google chrome")
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)

    def test_open_app_empty_returns_false(self):
        from core import actions
        ok, msg = actions.open_app("")
        self.assertFalse(ok)
        self.assertTrue("which" in msg.lower() or "what" in msg.lower())

    def test_write_note_returns_tuple(self):
        from core import actions
        content = "Test note from unit test"
        ok, msg = actions.write_note(content)
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)
        if ok:
            self.assertTrue("written" in msg.lower() or "notepad" in msg.lower())

    def test_write_note_empty_returns_false(self):
        from core import actions
        ok, msg = actions.write_note("")
        self.assertFalse(ok)
        self.assertGreater(len(msg), 0)

    def test_open_download_search_returns_tuple(self):
        from core import actions
        ok, msg = actions.open_download_search("vlc")
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)
        if ok:
            self.assertTrue("vlc" in msg.lower() or "search" in msg.lower() or "browser" in msg.lower())

    def test_open_download_search_empty_returns_false(self):
        from core import actions
        ok, msg = actions.open_download_search("")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
