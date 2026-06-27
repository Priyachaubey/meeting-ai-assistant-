# Audio Capture Notes

Desktop production clients should implement native capture per platform:

- Windows: WASAPI loopback or VB Cable routing
- macOS: ScreenCaptureKit, BlackHole, Loopback, or virtual audio device routing
- Linux: PipeWire/PulseAudio monitor sources

The backend expects PCM or transcript chunks and does not join meetings. Emergency stop must close device handles, end WebSocket streams and stop provider sessions.
