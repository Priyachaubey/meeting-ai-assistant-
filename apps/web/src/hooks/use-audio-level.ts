"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Detects whether a MediaStream's audio is currently above a speaking threshold, polled via
 * requestAnimationFrame against a Web Audio AnalyserNode. Built because the backend's
 * `is_speaking` field on the Participant model is declared but never actually set anywhere
 * (confirmed by reading every file in apps/meeting-server) — the frontend's active-speaker
 * ring highlight already existed and was correctly wired to that field, it just could never
 * fire. Rather than adding a new WS message type and a server-side VAD pass just to flip a
 * boolean the client can determine perfectly well on its own from the audio it already has,
 * this computes it directly per-tile, client-side, with zero backend involvement — exactly
 * the kind of thing that doesn't need round-tripping through a server.
 */
export function useAudioLevel(stream: MediaStream | null | undefined): boolean {
  const [isSpeaking, setIsSpeaking] = useState(false);

  useEffect(() => {
    if (!stream || stream.getAudioTracks().length === 0) {
      setIsSpeaking(false);
      return;
    }

    let audioContext: AudioContext | null = null;
    let rafId: number;
    let cancelled = false;
    // A short streak of frames above threshold, not a single one — raw audio level is noisy
    // frame-to-frame (a single loud click would otherwise flash the ring on/off); requiring
    // a few consecutive above-threshold frames before flipping on, and a longer streak of
    // below-threshold frames before flipping off, gives a stable highlight instead of a
    // flickering one — the same hysteresis idea as a real noise gate.
    let aboveStreak = 0;
    let belowStreak = 0;
    const ON_THRESHOLD = 18;
    const ON_STREAK_NEEDED = 3;
    const OFF_STREAK_NEEDED = 12;

    try {
      audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.6;
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        if (cancelled) return;
        analyser.getByteFrequencyData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) sum += data[i];
        const average = sum / data.length;

        if (average > ON_THRESHOLD) {
          aboveStreak++;
          belowStreak = 0;
          if (aboveStreak >= ON_STREAK_NEEDED) setIsSpeaking(true);
        } else {
          belowStreak++;
          aboveStreak = 0;
          if (belowStreak >= OFF_STREAK_NEEDED) setIsSpeaking(false);
        }
        rafId = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // Some streams (a screen-share track with no audio, a track mid-teardown) can throw
      // on createMediaStreamSource — fail to "not speaking" rather than crash the tile.
      setIsSpeaking(false);
    }

    return () => {
      cancelled = true;
      if (rafId) cancelAnimationFrame(rafId);
      audioContext?.close();
    };
  }, [stream]);

  return isSpeaking;
}
