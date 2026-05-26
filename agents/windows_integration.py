"""
Windows app integration - Teams, Outlook, Office.
Uses pywin32 COM (no API keys, uses installed apps directly).
Falls back to PowerShell + pyautogui if COM unavailable.
"""
import subprocess
import sys
import os
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta


def _ps(script: str, timeout: int = 15) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"


class OutlookIntegration:
    def _outlook(self):
        try:
            import win32com.client
            return win32com.client.Dispatch("Outlook.Application")
        except ImportError:
            raise RuntimeError("pywin32 not installed. Run: pip install pywin32")
        except Exception as e:
            raise RuntimeError(f"Outlook not available: {e}")

    def check_latest_email(self, from_filter: str = None) -> dict:
        try:
            ol   = self._outlook()
            ns   = ol.GetNamespace("MAPI")
            box  = ns.GetDefaultFolder(6)   # 6 = Inbox
            msgs = box.Items
            msgs.Sort("[ReceivedTime]", True)

            for i in range(min(50, msgs.Count)):
                m = msgs[i + 1]
                sender = str(m.SenderEmailAddress).lower()
                if from_filter and from_filter.lower() not in sender:
                    continue
                return {
                    "subject":  m.Subject,
                    "from":     m.SenderEmailAddress,
                    "received": str(m.ReceivedTime)[:16],
                    "body":     m.Body[:300].strip(),
                    "unread":   m.UnRead,
                }
            return {"error": "No matching email found"}
        except Exception as e:
            return {"error": str(e)}

    def send_email(self, to: str, subject: str, body: str) -> bool:
        try:
            ol   = self._outlook()
            mail = ol.CreateItem(0)
            mail.To      = to
            mail.Subject = subject
            mail.Body    = body
            mail.Send()
            return True
        except Exception as e:
            print(f"[Outlook] Send error: {e}")
            return False

    def get_todays_events(self) -> list:
        try:
            ol  = self._outlook()
            ns  = ol.GetNamespace("MAPI")
            cal = ns.GetDefaultFolder(9)   # 9 = Calendar
            now = datetime.now()
            end = now.replace(hour=23, minute=59)
            items = cal.Items
            items.IncludeRecurrences = True
            items.Sort("[Start]")
            events = []
            for item in items:
                try:
                    s = item.Start.replace(tzinfo=None)
                    if now.date() == s.date():
                        events.append({
                            "subject":  item.Subject,
                            "start":    str(item.Start)[11:16],
                            "end":      str(item.End)[11:16],
                            "location": item.Location or "No location",
                        })
                except Exception:
                    continue
            return events[:10]
        except Exception as e:
            return [{"error": str(e)}]


class TeamsIntegration:
    def create_meeting(self, title: str,
                       start_time: str, end_time: str) -> bool:
        """
        Create a Teams meeting.
        Uses Teams URI protocol - no API key needed, no auth needed.
        Opens Teams new meeting form with pre-filled title.
        """
        import urllib.parse
        enc_title = urllib.parse.quote(title)

        # Method 1: Teams URI (works if Teams installed)
        uri = f"msteams://teams.microsoft.com/l/meeting/new?subject={enc_title}"
        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    ["cmd", "/c", "start", "", uri],
                    shell=False, creationflags=0x00000008
                )
                time.sleep(3)
                # Auto-fill time via pyautogui
                try:
                    import pyautogui
                    pyautogui.hotkey("tab")
                    time.sleep(0.3)
                    pyautogui.typewrite(start_time, interval=0.05)
                except Exception:
                    pass
                return True
        except Exception as e:
            print(f"[Teams] URI method error: {e}")

        # Method 2: Open Teams and use new meeting shortcut
        try:
            subprocess.Popen(["Teams.exe"])
            time.sleep(4)
            import pyautogui
            pyautogui.hotkey("ctrl", "shift", "k")  # New meeting in Teams
            time.sleep(1)
            pyautogui.typewrite(title, interval=0.05)
            return True
        except Exception as e:
            print(f"[Teams] Automation error: {e}")
            return False


class WindowsApps:
    """Open and type in Windows apps using pyautogui."""

    def open_and_dictate(self, app_name: str, tts, lang: str = "en"):
        """Open an app and start dictation mode."""
        app_map = {
            "notepad":  "notepad.exe",
            "word":     "winword",
            "wordpad":  "wordpad.exe",
            "excel":    "excel",
            "paint":    "mspaint.exe",
        }
        exe = app_map.get(app_name.lower(), "notepad.exe")
        try:
            subprocess.Popen(exe)
            time.sleep(2)
            tts.speak(
                f"{app_name} is open. Say what you want to type. "
                f"Say save file when done.", lang
            )
            return True
        except Exception as e:
            tts.speak(f"Could not open {app_name}.", lang)
            return False

    def type_text(self, text: str):
        """Type text into currently focused window."""
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.04)
            return True
        except Exception as e:
            print(f"[Type] Error: {e}")
            return False

    def save_file(self, path: str = None):
        """Save current file. Ask for path if not given."""
        import pyautogui
        if path:
            pyautogui.hotkey("ctrl", "shift", "s")
            time.sleep(1)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.3)
            pyautogui.typewrite(path, interval=0.05)
            pyautogui.press("enter")
        else:
            pyautogui.hotkey("ctrl", "s")
