"""Voice Activity Detection using energy-based thresholding.

Analyzes PCM16 audio frames to detect speech activity by computing
the short-time energy and comparing against an adaptive threshold.
This is a simple but effective approach that works without ML models.
"""

from __future__ import annotations

import math
import struct


class VoiceActivityDetector:
    """Energy-based voice activity detector for PCM16 audio.

    Uses short-time energy with an adaptive threshold to distinguish
    speech from silence/background noise. The threshold adapts over
    time to handle varying noise levels.
    """

    def __init__(
        self,
        *,
        energy_threshold: float = 300.0,
        frame_size: int = 512,
        adaptive: bool = True,
        min_speech_frames: int = 3,
    ) -> None:
        self._base_threshold = energy_threshold
        self._threshold = energy_threshold
        self._frame_size = frame_size
        self._adaptive = adaptive
        self._min_speech_frames = min_speech_frames
        self._speech_count = 0
        self._noise_floor = 100.0
        self._frame_count = 0

    def is_user_speaking(self, pcm_frame: bytes) -> bool:
        """Detect if the PCM16 audio frame contains speech.

        Computes the RMS energy of the frame and compares against
        an adaptive threshold. Requires multiple consecutive frames
        above threshold to declare speech (reduces false positives).
        """
        if not pcm_frame or len(pcm_frame) < 2:
            self._speech_count = 0
            return False

        num_samples = len(pcm_frame) // 2
        try:
            samples = struct.unpack(f"<{num_samples}h", pcm_frame[: num_samples * 2])
        except struct.error:
            return False

        # Compute RMS energy
        energy = math.sqrt(sum(s * s for s in samples) / max(num_samples, 1))

        # Update noise floor (running minimum)
        self._frame_count += 1
        if energy < self._noise_floor:
            self._noise_floor = energy
        elif self._frame_count % 100 == 0:
            # Slowly increase noise floor toward current energy if consistently quiet
            self._noise_floor = self._noise_floor * 0.99 + energy * 0.01

        # Adaptive threshold: noise floor * multiplier, but at least base_threshold
        if self._adaptive:
            self._threshold = max(self._base_threshold, self._noise_floor * 4.0)

        is_active = energy > self._threshold

        if is_active:
            self._speech_count += 1
        else:
            self._speech_count = max(0, self._speech_count - 1)

        # Require multiple consecutive active frames to declare speech
        return self._speech_count >= self._min_speech_frames

    @property
    def current_threshold(self) -> float:
        return self._threshold

    @property
    def noise_floor(self) -> float:
        return self._noise_floor

    def reset(self) -> None:
        """Reset the detector state."""
        self._speech_count = 0
        self._noise_floor = 100.0
        self._threshold = self._base_threshold
        self._frame_count = 0
