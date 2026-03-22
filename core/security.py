# -*- coding: utf-8 -*-
"""Security: monitor applications, scan installed apps, detect unwanted/dangerous. Owner data stays local."""

import os
import json
import hashlib
import threading
import time
from typing import Callable, Optional
import config.settings as settings

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False


class SecurityMonitor:
    """Monitors running processes and installed apps; detects unwanted/dangerous. All data stays on device."""

    def __init__(self, on_threat: Optional[Callable[[str, str], None]] = None):
        self.on_threat = on_threat  # callback(process_name_or_path, reason)
        self.blocklist_path = settings.BLOCKLIST_DB
        self._blocklist: set[str] = set()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._load_blocklist()

    def _load_blocklist(self) -> None:
        if os.path.isfile(self.blocklist_path):
            try:
                with open(self.blocklist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._blocklist = set(data.get("blocked_names", []) + data.get("blocked_hashes", []))
            except Exception:
                self._blocklist = set()
        else:
            os.makedirs(os.path.dirname(self.blocklist_path), exist_ok=True)

    def _save_blocklist(self) -> None:
        try:
            names = [x for x in self._blocklist if not len(x) == 64 or not all(c in "0123456789abcdef" for c in x)]
            hashes = [x for x in self._blocklist if len(x) == 64 and all(c in "0123456789abcdef" for c in x)]
            with open(self.blocklist_path, "w", encoding="utf-8") as f:
                json.dump({"blocked_names": names, "blocked_hashes": hashes}, f, indent=2)
        except Exception:
            pass

    def block_process(self, name_or_hash: str) -> None:
        self._blocklist.add(name_or_hash.strip())
        self._save_blocklist()

    def get_running_processes(self) -> list[dict]:
        """List running processes (name, exe path, pid). No data leaves the system."""
        if not PSUTIL_AVAILABLE:
            return []
        result = []
        try:
            for p in psutil.process_iter(["name", "exe", "pid"]):
                try:
                    info = p.info
                    result.append({
                        "name": info.get("name") or "",
                        "exe": info.get("exe") or "",
                        "pid": info.get("pid"),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return result

    def get_installed_apps(self) -> list[dict]:
        """List installed apps from Windows registry. Local only."""
        if not WINREG_AVAILABLE:
            return []
        result = []
        uninstall_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.OpenKey(hkey, uninstall_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        name = winreg.EnumKey(key, i)
                        sub = winreg.OpenKey(key, name)
                        display = winreg.QueryValueEx(sub, "DisplayName")[0]
                        result.append({"name": display, "key": name})
                    except (WindowsError, OSError, FileNotFoundError):
                        pass
            except (WindowsError, OSError):
                pass
        return result

    def _file_hash(self, path: str) -> str:
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read(1024 * 1024)).hexdigest()
        except Exception:
            return ""

    def _is_suspicious_name(self, name: str) -> bool:
        """Heuristic: known risky patterns (no cloud lookup)."""
        n = name.lower()
        risky = (
            "keygen", "crack", "patch", "torrent", "miner", "crypto",
            "injector", "loader", "stealer", "rat", "backdoor", "trojan",
        )
        return any(r in n for r in risky)

    def scan_running(self) -> list[dict]:
        """Scan running processes for blocklist and suspicious names. Returns list of threats."""
        threats = []
        for p in self.get_running_processes():
            name = (p.get("name") or "").strip()
            exe = (p.get("exe") or "").strip()
            if name in self._blocklist or exe in self._blocklist:
                threats.append({"type": "blocked", "name": name, "path": exe})
            elif self._is_suspicious_name(name) or self._is_suspicious_name(os.path.basename(exe)):
                threats.append({"type": "suspicious", "name": name, "path": exe})
            else:
                h = self._file_hash(exe) if exe and os.path.isfile(exe) else ""
                if h and h in self._blocklist:
                    threats.append({"type": "blocked_hash", "name": name, "path": exe})
        return threats

    def _monitor_loop(self) -> None:
        while self._running:
            for t in self.scan_running():
                if self.on_threat:
                    self.on_threat(t.get("name") or t.get("path", ""), t.get("type", "unknown"))
            time.sleep(settings.MONITOR_INTERVAL_SEC)

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
