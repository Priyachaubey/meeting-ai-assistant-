# Architecture

Microtechnique AI Meeting uses a local-first capture model. The app listens to system audio through OS-level routing such as VB Cable, BlackHole, Loopback, WASAPI loopback, ScreenCaptureKit, PipeWire, or PulseAudio monitor sources. Audio frames are processed by VAD, forwarded to transcription providers, converted into transcript events, and streamed through WebSockets.

## Agent Flow

1. Question Detection Agent classifies transcript chunks.
2. Context Agent gathers meeting mode, recent utterances, speaker and account context.
3. Knowledge Retrieval Agent searches Qdrant for private context.
4. Response Generation Agent calls the configured model provider.
5. Summary, Action Item, Sentiment and Intelligence Agents enrich the meeting record.

PostgreSQL stores users, meetings, transcript events and document metadata. Qdrant stores embeddings. Redis powers Celery jobs, transient sessions and rate limits.
