"""
Voice Authentication System for ASTRA
Only accepts commands from the enrolled user's voice.
Uses voice embeddings to verify speaker identity.
"""
import os
import sys
import json
import numpy as np
import wave
import tempfile
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = ROOT / "data" / "voice_samples"
EMBEDDINGS_FILE = ROOT / "data" / "voice_embeddings.json"


class VoiceAuthenticator:
    """
    Voice authentication using speaker embeddings.
    Compares incoming voice with enrolled user's voice samples.
    """
    
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold
        self.enrolled_embeddings = []
        self.enabled = False
        self._encoder = None
        
        self._load_enrollments()
    
    def _load_encoder(self):
        """Load speaker encoder model (lazy loading)."""
        if self._encoder is not None:
            return True
        
        try:
            from resemblyzer import VoiceEncoder, preprocess_wav
            self._encoder = VoiceEncoder()
            self._preprocess = preprocess_wav
            print("[VoiceAuth] Speaker encoder loaded")
            return True
        except ImportError:
            print("[VoiceAuth] resemblyzer not installed. Voice auth disabled.")
            print("[VoiceAuth] Install with: pip install resemblyzer")
            return False
    
    def _load_enrollments(self):
        """Load enrolled voice embeddings."""
        if EMBEDDINGS_FILE.exists():
            try:
                data = json.loads(EMBEDDINGS_FILE.read_text())
                self.enrolled_embeddings = [np.array(e) for e in data.get("embeddings", [])]
                self.enabled = len(self.enrolled_embeddings) >= 3
                print(f"[VoiceAuth] Loaded {len(self.enrolled_embeddings)} voice embeddings")
            except Exception as e:
                print(f"[VoiceAuth] Could not load embeddings: {e}")
    
    def enroll_samples(self, sample_paths: list) -> bool:
        """
        Enroll user voice from sample files.
        Requires at least 3 samples for good accuracy.
        """
        if not self._load_encoder():
            return False
        
        embeddings = []
        for path in sample_paths:
            try:
                wav = self._preprocess(Path(path))
                embed = self._encoder.embed_utterance(wav)
                embeddings.append(embed)
            except Exception as e:
                print(f"[VoiceAuth] Failed to process {path}: {e}")
        
        if len(embeddings) < 3:
            print("[VoiceAuth] Need at least 3 valid samples")
            return False
        
        self.enrolled_embeddings = embeddings
        self.enabled = True
        
        # Save embeddings
        EMBEDDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {"embeddings": [e.tolist() for e in embeddings]}
        EMBEDDINGS_FILE.write_text(json.dumps(data))
        
        print(f"[VoiceAuth] Enrolled {len(embeddings)} voice samples")
        return True
    
    def verify(self, audio_bytes: bytes) -> Tuple[bool, float]:
        """
        Verify if audio matches enrolled user.
        Returns (is_match, confidence_score).
        """
        if not self.enabled:
            return True, 1.0  # Not enabled, allow all
        
        if not self._load_encoder():
            return True, 1.0  # Encoder not available, allow
        
        if not self.enrolled_embeddings:
            return True, 1.0  # No enrollments
        
        try:
            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            
            # Get embedding
            wav = self._preprocess(Path(tmp_path))
            embed = self._encoder.embed_utterance(wav)
            
            # Clean up
            os.unlink(tmp_path)
            
            # Compare with enrolled embeddings
            similarities = []
            for enrolled in self.enrolled_embeddings:
                sim = np.dot(embed, enrolled) / (np.linalg.norm(embed) * np.linalg.norm(enrolled))
                similarities.append(sim)
            
            # Use max similarity
            confidence = max(similarities)
            is_match = confidence >= self.threshold
            
            if not is_match:
                print(f"[VoiceAuth] Voice rejected (confidence: {confidence:.2f})")
            
            return is_match, confidence
            
        except Exception as e:
            print(f"[VoiceAuth] Verification error: {e}")
            return True, 1.0  # On error, allow
    
    def is_enabled(self) -> bool:
        """Check if voice auth is enabled."""
        return self.enabled and len(self.enrolled_embeddings) >= 3


class SimpleVoiceAuth:
    """
    Simple voice authentication using audio energy patterns.
    Less accurate but works without additional dependencies.
    """
    
    def __init__(self):
        self.enabled = False
        self.reference_patterns = []
        self._load_patterns()
    
    def _load_patterns(self):
        """Load reference voice patterns."""
        pattern_file = ROOT / "data" / "voice_patterns.json"
        if pattern_file.exists():
            try:
                data = json.loads(pattern_file.read_text())
                self.reference_patterns = data.get("patterns", [])
                self.enabled = len(self.reference_patterns) >= 3
            except Exception:
                pass
    
    def _extract_pattern(self, audio_bytes: bytes) -> list:
        """Extract simple audio pattern (energy over time)."""
        try:
            # Parse WAV header
            audio = np.frombuffer(audio_bytes[44:], dtype=np.int16)  # Skip WAV header
            
            # Divide into chunks and calculate RMS
            chunk_size = len(audio) // 20
            if chunk_size < 100:
                return []
            
            pattern = []
            for i in range(20):
                chunk = audio[i*chunk_size:(i+1)*chunk_size]
                rms = np.sqrt(np.mean(chunk.astype(float)**2))
                pattern.append(float(rms))
            
            # Normalize
            max_val = max(pattern) or 1
            pattern = [p / max_val for p in pattern]
            
            return pattern
        except Exception:
            return []
    
    def enroll(self, sample_paths: list) -> bool:
        """Enroll voice patterns from samples."""
        patterns = []
        
        for path in sample_paths:
            try:
                audio_bytes = Path(path).read_bytes()
                pattern = self._extract_pattern(audio_bytes)
                if pattern:
                    patterns.append(pattern)
            except Exception:
                continue
        
        if len(patterns) < 3:
            return False
        
        self.reference_patterns = patterns
        self.enabled = True
        
        # Save
        pattern_file = ROOT / "data" / "voice_patterns.json"
        pattern_file.parent.mkdir(parents=True, exist_ok=True)
        pattern_file.write_text(json.dumps({"patterns": patterns}))
        
        return True
    
    def verify(self, audio_bytes: bytes) -> Tuple[bool, float]:
        """Verify voice using simple pattern matching."""
        if not self.enabled or not self.reference_patterns:
            return True, 1.0
        
        pattern = self._extract_pattern(audio_bytes)
        if not pattern:
            return True, 1.0
        
        # Compare with reference patterns
        similarities = []
        for ref in self.reference_patterns:
            if len(ref) != len(pattern):
                continue
            # Correlation coefficient
            corr = np.corrcoef(pattern, ref)[0, 1]
            similarities.append(corr if not np.isnan(corr) else 0)
        
        if not similarities:
            return True, 1.0
        
        confidence = max(similarities)
        is_match = confidence >= 0.6  # Lower threshold for simple method
        
        return is_match, confidence


def get_voice_authenticator():
    """
    Get the best available voice authenticator.
    Tries advanced (resemblyzer) first, falls back to simple.
    """
    try:
        from resemblyzer import VoiceEncoder
        return VoiceAuthenticator()
    except ImportError:
        print("[VoiceAuth] Using simple voice authentication")
        return SimpleVoiceAuth()
