"""
Screen analyzer - NO API KEY needed.
Uses local LLM (Ollama vision models) OR pixel/window analysis fallback.
Methods:
  1. llava model via Ollama (free, local, has vision)
  2. pytesseract OCR - reads text from screen
  3. Window title + process analysis
"""
import subprocess
import sys
import os
import base64
import tempfile
import json
from pathlib import Path


def _capture_screen() -> str:
    """Capture screen and return base64 PNG."""
    try:
        import pyautogui
        from PIL import Image
        import io
        screenshot = pyautogui.screenshot()
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"[Screen] Capture error: {e}")
        return ""


def _read_screen_text() -> str:
    """Extract text from screen using OCR - no API needed."""
    try:
        import pyautogui
        import pytesseract
        from PIL import Image

        screenshot = pyautogui.screenshot()
        # Resize for faster OCR
        w, h = screenshot.size
        screenshot = screenshot.resize((w // 2, h // 2))
        text = pytesseract.image_to_string(screenshot)
        # Clean up
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 3]
        return "\n".join(lines[:30])
    except ImportError:
        return ""
    except Exception as e:
        return f"OCR error: {e}"


def _get_active_window() -> dict:
    """Get currently active window info."""
    info = {"title": "", "process": "", "apps": []}
    if sys.platform != "win32":
        return info
    try:
        ps = subprocess.run(
            ["powershell", "-Command",
             "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
             "Select-Object ProcessName,MainWindowTitle,CPU | "
             "Sort-Object CPU -Descending | "
             "Select-Object -First 5 | ConvertTo-Json"],
            capture_output=True, text=True, timeout=8
        )
        if ps.returncode == 0 and ps.stdout.strip():
            raw = ps.stdout.strip()
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            info["apps"] = [
                f"{d.get('ProcessName','?')}: {d.get('MainWindowTitle','')}"
                for d in data if d.get("MainWindowTitle")
            ]
            if info["apps"]:
                first = info["apps"][0]
                info["title"]   = first.split(":", 1)[-1].strip()
                info["process"] = first.split(":", 1)[0].strip()
    except Exception as e:
        print(f"[Screen] Window info error: {e}")
    return info


def _analyze_with_llava(img_b64: str, llm_engine) -> str:
    """Use Ollama llava model for vision - completely free and local."""
    try:
        import ollama
        # Check if llava is available
        models = [m["name"] for m in ollama.list().get("models", [])]
        vision_model = None
        for m in models:
            if "llava" in m.lower() or "bakllava" in m.lower() or "moondream" in m.lower():
                vision_model = m
                break

        if not vision_model:
            return None  # No vision model

        resp = ollama.chat(
            model=vision_model,
            messages=[{
                "role": "user",
                "content": ("Look at this screen. In 2 short sentences: "
                            "what is the user doing, and is there anything "
                            "obviously wrong or improvable?"),
                "images": [img_b64],
            }]
        )
        return resp["message"]["content"]
    except Exception:
        return None


def analyze_screen(llm_engine=None) -> str:
    """
    Full screen analysis pipeline - no API key needed.
    1. Try Ollama vision model (llava/moondream)
    2. OCR text extraction + LLM analysis
    3. Window context analysis
    """
    results = []

    # Get active window context
    win = _get_active_window()
    if win["apps"]:
        results.append(f"Open apps: {', '.join(win['apps'][:3])}")
        results.append(f"Active window: {win['title']}")

    # Try vision model first
    img_b64 = _capture_screen()
    if img_b64 and llm_engine:
        vision_result = _analyze_with_llava(img_b64, llm_engine)
        if vision_result:
            return f"I can see your screen. {vision_result}"

    # OCR fallback
    screen_text = _read_screen_text()
    if screen_text and llm_engine:
        context = "\n".join(results)
        prompt = (
            f"The user's screen shows these open apps: {context}\n"
            f"Screen text (via OCR): {screen_text[:800]}\n\n"
            f"In 2 sentences: what is the user doing and any suggestions? "
            f"Plain text only, no markdown."
        )
        try:
            answer = llm_engine.simple_query(prompt)
            return answer
        except Exception:
            pass

    # Basic window context only
    if results:
        apps_str = ", ".join(win["apps"][:3])
        return f"You have these apps open: {apps_str}. Tell me what you want to do with them."

    return "I can see your screen but could not extract useful information. Try installing pytesseract for better screen reading."


def install_vision_model():
    """Pull moondream2 - smallest vision model, works on 4GB VRAM."""
    print("[Screen] Pulling moondream2 vision model (1.7GB)...")
    result = subprocess.run(["ollama", "pull", "moondream"], capture_output=False)
    return result.returncode == 0
