# -*- coding: utf-8 -*-
"""System actions: open apps, write notes, web search, open URLs, download search."""

import os
import sys
import subprocess
import tempfile
import platform
from urllib.parse import quote

# Windows app names -> launch command or path (use shell for start so Windows finds apps)
_WIN_APPS = {
    "notepad": ["notepad"],
    "notepad plus plus": ["notepad++"],
    "chrome": "start chrome",
    "google chrome": "start chrome",
    "firefox": "start firefox",
    "edge": "start msedge",
    "microsoft edge": "start msedge",
    "calculator": ["calc"],
    "calc": ["calc"],
    "paint": ["mspaint"],
    "file explorer": ["explorer"],
    "explorer": ["explorer"],
    "command prompt": ["cmd"],
    "cmd": ["cmd"],
    "powershell": ["powershell"],
    "task manager": ["taskmgr"],
    "settings": ["cmd", "/c", "start", "ms-settings:"],
    "control panel": ["control"],
    "microsoft word": "start winword",
    "word": "start winword",
    "winword": "start winword",
    "ms word": "start winword",
    "microsoft excel": "start excel",
    "excel": "start excel",
    "microsoft powerpoint": "start powerpnt",
    "powerpoint": "start powerpnt",
    "power point": "start powerpnt",
}

# Common sites: spoken name -> URL (open youtube, open gmail, etc.)
_COMMON_SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "outlook": "https://outlook.live.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "wiki": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "maps": "https://www.google.com/maps",
    "google maps": "https://www.google.com/maps",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "calendar": "https://calendar.google.com",
    "google calendar": "https://calendar.google.com",
}

# Drive phrases: "d drive", "drive d" -> letter for explorer D:\
_DRIVE_PHRASES = {
    "a drive": "a", "drive a": "a",
    "b drive": "b", "drive b": "b",
    "c drive": "c", "drive c": "c",
    "d drive": "d", "drive d": "d",
    "e drive": "e", "drive e": "e",
    "f drive": "f", "drive f": "f",
}


def open_drive(letter: str) -> tuple[bool, str]:
    """Open File Explorer to a drive (e.g. D:). Letter should be a single character A-Z."""
    letter = (letter or "").strip().upper()
    if not letter or len(letter) != 1 or letter not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        return False, "Which drive? Say for example: open D drive."
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", f"{letter}:\\"], shell=False)
            return True, f"Opened {letter} drive."
        return False, "Opening a drive is supported on Windows."
    except Exception as e:
        return False, f"Could not open drive: {e}"


def open_cmd_with_command(command: str) -> tuple[bool, str]:
    """Open Command Prompt and run a command (e.g. pip install requests). Windows only."""
    command = (command or "").strip()
    if not command:
        return False, "What command should I run in Command Prompt?"
    try:
        if platform.system() == "Windows":
            subprocess.Popen(f'start cmd /k "{command}"', shell=True)
            return True, f"Opened Command Prompt and running: {command[:50]}."
        return False, "Run command in terminal is supported on Windows."
    except Exception as e:
        return False, f"Could not open Command Prompt: {e}"


def open_path(path: str) -> tuple[bool, str]:
    """Open File Explorer to a folder path (e.g. D:\\Videos\\Movies). Windows only."""
    path = (path or "").strip()
    if not path:
        return False, "Which folder path should I open?"
    try:
        if platform.system() == "Windows":
            path = path.replace("/", "\\")
            if not os.path.isabs(path) and ":" not in path[:2]:
                path = os.path.abspath(path)
            subprocess.Popen(["explorer", path], shell=False)
            return True, f"Opened {path[:50]}."
        return False, "Opening a path is supported on Windows."
    except Exception as e:
        return False, f"Could not open path: {e}"


def open_or_run_file(path: str) -> tuple[bool, str]:
    """Open or run a file (folder, app, movie, etc.) with default handler. Windows: os.startfile."""
    path = (path or "").strip().replace("/", "\\")
    if not path:
        return False, "Which file or folder should I open?"
    try:
        if platform.system() == "Windows":
            if os.path.exists(path):
                os.startfile(path)
                return True, f"Opened {os.path.basename(path)[:40]}."
            return False, f"Path not found: {path[:50]}."
        return False, "Open file is supported on Windows."
    except Exception as e:
        return False, f"Could not open: {e}"


def search_youtube(query: str) -> tuple[bool, str]:
    """Open YouTube search results for the given query."""
    query = (query or "").strip()
    if not query:
        return False, "What should I search for on YouTube?"
    try:
        import webbrowser
        url = f"https://www.youtube.com/results?search_query={quote(query)}"
        webbrowser.open(url)
        return True, f"Searching YouTube for {query[:40]}."
    except Exception as e:
        return False, f"Could not open YouTube: {e}"


def open_learn_language(lang: str) -> tuple[bool, str]:
    """Open browser to learn a language (search or Duolingo)."""
    lang = (lang or "").strip()
    if not lang:
        return False, "Which language do you want to learn?"
    try:
        import webbrowser
        url = f"https://www.google.com/search?q={quote('learn ' + lang + ' language')}"
        webbrowser.open(url)
        return True, f"Opened search for learning {lang}. You can try Duolingo or other sites."
    except Exception as e:
        return False, f"Could not open browser: {e}"


def open_app(name: str) -> tuple[bool, str]:
    """
    Open an application by name, or a known website (youtube, gmail, etc.). Returns (success, message).
    """
    name_clean = name.strip().lower()
    if not name_clean:
        return False, "Which app should I open?"

    # Open drive: "D drive", "drive D", "C drive", etc.
    if name_clean in _DRIVE_PHRASES:
        return open_drive(_DRIVE_PHRASES[name_clean])

    # Known website: open in browser
    if name_clean in _COMMON_SITES:
        return open_url(name_clean)

    def _launch(cmd) -> bool:
        try:
            if isinstance(cmd, str):
                subprocess.Popen(cmd, shell=True)
                return True
            flags = (subprocess.CREATE_NO_WINDOW if (os.name == "nt" and cmd and cmd[0] == "cmd") else 0)
            subprocess.Popen(cmd, shell=False, creationflags=flags)
            return True
        except Exception:
            return False

    # Direct match
    if name_clean in _WIN_APPS:
        cmd = _WIN_APPS[name_clean]
        if _launch(cmd):
            return True, f"Opened {name_clean}."
        if name_clean in ("chrome", "google chrome", "firefox", "edge", "microsoft edge"):
            try:
                import webbrowser
                webbrowser.open("https://www.google.com")
                return True, "Opened your browser."
            except Exception:
                pass
        return False, f"Could not open {name_clean}. Try opening it from the Start menu."

    # Partial match (e.g. "open the google chrome" -> "google chrome")
    for key in _WIN_APPS:
        if key in name_clean or name_clean in key:
            cmd = _WIN_APPS[key]
            if _launch(cmd):
                return True, f"Opened {key}."
            if key in ("chrome", "google chrome", "firefox", "edge", "microsoft edge"):
                try:
                    import webbrowser
                    webbrowser.open("https://www.google.com")
                    return True, "Opened your browser."
                except Exception:
                    pass
            return False, f"Could not open {key}. Try opening it from the Start menu."

    # Try as raw command (e.g. "open spotify" if we add it)
    try:
        subprocess.Popen(name_clean, shell=True)
        return True, f"Opened {name_clean}."
    except Exception:
        return False, f"I don't know how to open '{name}'. Try: Notepad, Chrome, Calculator, File Explorer."


def write_note(content: str) -> tuple[bool, str]:
    """
    Write text to a new Notepad file and open it. Returns (success, message).
    """
    content = (content or "").strip()
    if not content:
        return False, "What would you like me to write in the note?"

    try:
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="jarvis_note_", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            os.close(fd)
            raise
        if platform.system() == "Windows":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path] if sys.platform != "darwin" else ["open", "-e", path])
        return True, "I've written that in Notepad. You can save it wherever you like."
    except Exception as e:
        return False, f"Could not create the note: {e}"


def open_web_search(query: str) -> tuple[bool, str]:
    """
    Open default browser with a Google search for the given query.
    Use for: "search for X", "google X", "look up X". Returns (success, message).
    """
    query = (query or "").strip()
    if not query:
        return False, "What would you like me to search for?"

    try:
        import webbrowser
        url = f"https://www.google.com/search?q={quote(query)}"
        webbrowser.open(url)
        return True, f"Searching for {query[:50]}."
    except Exception as e:
        return False, f"Could not open browser: {e}"


def open_url(site_or_url: str) -> tuple[bool, str]:
    """
    Open a website by name (e.g. youtube, gmail) or full URL.
    Returns (success, message).
    """
    raw = (site_or_url or "").strip()
    if not raw:
        return False, "Which website should I open?"

    try:
        import webbrowser
        key = raw.lower().strip()
        if key in _COMMON_SITES:
            url = _COMMON_SITES[key]
            try:
                webbrowser.open(url)
            except Exception:
                if platform.system() == "Windows" and hasattr(os, "startfile"):
                    os.startfile(url)
                else:
                    raise
            return True, f"Opened {key}."
        if key.startswith("http://") or key.startswith("https://"):
            try:
                webbrowser.open(raw)
            except Exception:
                if platform.system() == "Windows" and hasattr(os, "startfile"):
                    os.startfile(raw)
                else:
                    raise
            return True, "Opened the link."
        # Treat as search if it looks like a phrase (e.g. "prime travel")
        url = f"https://www.google.com/search?q={quote(raw)}"
        webbrowser.open(url)
        return True, f"Searching for {raw[:50]}."
    except Exception as e:
        return False, f"Could not open browser: {e}"


def open_download_search(software_name: str) -> tuple[bool, str]:
    """
    Open default browser with a Google search for '[software_name] download'.
    Returns (success, message).
    """
    software_name = (software_name or "").strip()
    if not software_name:
        return False, "Which software do you want to download?"

    try:
        import webbrowser
        query = quote(f"{software_name} download official")
        url = f"https://www.google.com/search?q={query}"
        webbrowser.open(url)
        return True, f"I've opened a search for {software_name} download. Choose the version you need and run the installer when it finishes downloading."
    except Exception as e:
        return False, f"Could not open browser: {e}"
