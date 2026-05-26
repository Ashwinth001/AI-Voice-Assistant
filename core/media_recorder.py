"""
ASTRA Media Recorder
Camera, video recording, and screen capture.
Saves to standard user folders (Pictures, Videos).
"""
import os
import sys
import threading
import time
from pathlib import Path
from datetime import datetime

from core.config_loader import load_config

_cfg = load_config()

# Output directories
PICTURES_DIR = Path(_cfg.get("media", {}).get("pictures_folder", Path.home() / "Pictures" / "ASTRA"))
VIDEOS_DIR = Path(_cfg.get("media", {}).get("videos_folder", Path.home() / "Videos" / "ASTRA"))
SCREENSHOTS_DIR = Path(_cfg.get("media", {}).get("screenshots_folder", Path.home() / "Pictures" / "ASTRA_Screenshots"))

# Create directories
for d in [PICTURES_DIR, VIDEOS_DIR, SCREENSHOTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class CameraRecorder:
    """
    Camera access and photo/video recording.
    """
    
    def __init__(self):
        self._cap = None
        self._recording = False
        self._video_writer = None
        self._record_thread = None
    
    def _get_camera(self):
        """Get camera capture object."""
        if self._cap is None:
            try:
                import cv2
                self._cap = cv2.VideoCapture(0)
                if not self._cap.isOpened():
                    print("[Camera] Could not open camera")
                    self._cap = None
            except ImportError:
                print("[Camera] opencv-python not installed. Run: pip install opencv-python")
                return None
        return self._cap
    
    def take_photo(self) -> str:
        """Take a photo and save to Pictures folder."""
        cap = self._get_camera()
        if cap is None:
            return None
        
        try:
            import cv2
            
            # Warm up camera
            for _ in range(5):
                cap.read()
            
            ret, frame = cap.read()
            if not ret:
                print("[Camera] Failed to capture frame")
                return None
            
            # Save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_{timestamp}.jpg"
            filepath = PICTURES_DIR / filename
            
            cv2.imwrite(str(filepath), frame)
            print(f"[Camera] Photo saved: {filepath}")
            
            return str(filepath)
            
        except Exception as e:
            print(f"[Camera] Error: {e}")
            return None
    
    def start_video_recording(self) -> bool:
        """Start video recording."""
        if self._recording:
            return False
        
        cap = self._get_camera()
        if cap is None:
            return False
        
        try:
            import cv2
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"video_{timestamp}.mp4"
            filepath = VIDEOS_DIR / filename
            
            # Get camera properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = 30
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self._video_writer = cv2.VideoWriter(str(filepath), fourcc, fps, (width, height))
            
            self._recording = True
            self._current_video = str(filepath)
            
            # Start recording thread
            def record():
                while self._recording:
                    ret, frame = cap.read()
                    if ret:
                        self._video_writer.write(frame)
                    time.sleep(1/fps)
            
            self._record_thread = threading.Thread(target=record, daemon=True)
            self._record_thread.start()
            
            print(f"[Camera] Recording started: {filepath}")
            return True
            
        except Exception as e:
            print(f"[Camera] Error starting recording: {e}")
            return False
    
    def stop_video_recording(self) -> str:
        """Stop video recording and return file path."""
        if not self._recording:
            return None
        
        self._recording = False
        
        if self._record_thread:
            self._record_thread.join(timeout=2)
        
        if self._video_writer:
            self._video_writer.release()
            self._video_writer = None
        
        filepath = getattr(self, '_current_video', None)
        print(f"[Camera] Recording saved: {filepath}")
        
        return filepath
    
    def release(self):
        """Release camera resources."""
        if self._recording:
            self.stop_video_recording()
        if self._cap:
            self._cap.release()
            self._cap = None


class ScreenRecorder:
    """
    Screen capture and recording.
    """
    
    def __init__(self):
        self._recording = False
        self._record_thread = None
        self._frames = []
    
    def take_screenshot(self) -> str:
        """Take a screenshot and save to Pictures folder."""
        try:
            import pyautogui
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = SCREENSHOTS_DIR / filename
            
            screenshot = pyautogui.screenshot()
            screenshot.save(str(filepath))
            
            print(f"[Screen] Screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"[Screen] Screenshot error: {e}")
            return None
    
    def start_screen_recording(self, fps: int = 15) -> bool:
        """Start screen recording."""
        if self._recording:
            return False
        
        try:
            import pyautogui
            import cv2
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screen_recording_{timestamp}.mp4"
            self._current_recording = str(VIDEOS_DIR / filename)
            
            # Get screen size
            screen = pyautogui.size()
            
            # Video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self._writer = cv2.VideoWriter(
                self._current_recording, fourcc, fps,
                (screen.width, screen.height)
            )
            
            self._recording = True
            
            def record():
                import numpy as np
                while self._recording:
                    img = pyautogui.screenshot()
                    frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                    self._writer.write(frame)
                    time.sleep(1/fps)
            
            self._record_thread = threading.Thread(target=record, daemon=True)
            self._record_thread.start()
            
            print(f"[Screen] Recording started: {self._current_recording}")
            return True
            
        except Exception as e:
            print(f"[Screen] Error: {e}")
            return False
    
    def stop_screen_recording(self) -> str:
        """Stop screen recording and return file path."""
        if not self._recording:
            return None
        
        self._recording = False
        
        if self._record_thread:
            self._record_thread.join(timeout=2)
        
        if hasattr(self, '_writer'):
            self._writer.release()
        
        filepath = getattr(self, '_current_recording', None)
        print(f"[Screen] Recording saved: {filepath}")
        
        return filepath


# Singleton instances
_camera = None
_screen = None


def get_camera_recorder() -> CameraRecorder:
    """Get camera recorder singleton."""
    global _camera
    if _camera is None:
        _camera = CameraRecorder()
    return _camera


def get_screen_recorder() -> ScreenRecorder:
    """Get screen recorder singleton."""
    global _screen
    if _screen is None:
        _screen = ScreenRecorder()
    return _screen
