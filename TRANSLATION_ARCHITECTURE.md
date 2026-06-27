# Real-Time Multilingual Translation — Architecture (Deliverable B)

This is the design for live, speaker-aware, per-participant-language audio translation. It's
split clearly into what's real code (built and tested in this pass) and what's a genuine
infrastructure/product dependency that doesn't exist yet — per the request that drove this:
classify honestly, don't skip implementation just because final validation needs
infra/credentials, but also don't claim something is "architecturally complete" when a load-
bearing piece of it (see §3) doesn't exist anywhere in this codebase.

## 1. Pipeline overview

```
 Deepgram (real, Phase 1)          Buffering (real, tested)         Translation (real, tested)         Fan-out (GAP — see §3)
┌─────────────────────┐     ┌──────────────────────────┐     ┌───────────────────────────┐     ┌─────────────────────────┐
│ finalized utterance  │──▶ │ UtteranceBuffer           │──▶ │ LiveTranslationCoordinator │──▶ │ per-participant delivery │
│ (speaker, text, ts)  │     │ per-speaker, gap+length   │     │ dedup target languages,    │     │ NEEDS: connection        │
│                       │     │ triggered flush           │     │ concurrent translate calls │     │ registry per meeting     │
└─────────────────────┘     └──────────────────────────┘     └───────────────────────────┘     └─────────────────────────┘
                                                                        │
                                                              ┌───────────────────┐
                                                              │ StreamingTranslation│ ← LLMTranslationProvider (real,
                                                              │ Provider interface  │   works today) or a specialized
                                                              └───────────────────┘   MT model (GAP — see §4)
```

## 2. What's real code in this pass (`app/services/translation/`)

- **`buffer.py` — `UtteranceBuffer`.** Per-speaker buffering: consecutive same-speaker
  utterances merge if the gap between them is short and the merged text hasn't hit a length
  cap; a long pause or hitting the cap flushes. Pure algorithm, zero I/O. 5 tests in
  `tests/test_translation_buffer.py`, all actually executed (not just `py_compile`'d) against
  synthetic timestamps during this build — merge-within-gap, flush-on-long-pause, flush-on-
  length-cap, independent per-speaker state, and full drain all verified to behave correctly.
- **`base.py` — `StreamingTranslationProvider`.** The contract any real-time MT backend
  implements: `translate(text, source_language, target_language) -> str`. Same pattern as
  `LLMProvider`/`TranscriptionProvider` elsewhere in this codebase — swap the implementation,
  nothing else changes.
- **`llm_provider.py` — `LLMTranslationProvider`.** A REAL, working implementation of that
  contract, not a stub — built from the LLM providers already wired in Phase 1 plus the
  `text_translation` prompt template (same one Deliverable A's `/api/ai/translate` uses).
  Honest tradeoff stated in its docstring: each call is a full LLM round-trip
  (~0.5-2+ seconds depending on provider/load), which will often hit "<2s" for one utterance
  but won't reliably at multi-speaker call volume. This exists so the rest of the pipeline has
  something real to run against today, not as a placeholder for something else.
- **`coordinator.py` — `LiveTranslationCoordinator`.** Ties buffer + provider together:
  flushes go out to every *distinct* requested target language (a `set`, so 5 participants
  all wanting Spanish costs one call, not five), fired concurrently via `asyncio.gather` so
  requesting 4 languages doesn't take 4x as long as requesting 1, with per-language failure
  isolation (one language's translation failing doesn't break the others). 3 tests in
  `tests/test_translation_coordinator.py`, actually executed with a fake provider and a
  simulated 50ms latency — confirmed real dedup (3 requests → 2 calls), real concurrency
  (3 languages in ~0.05s, not ~0.15s), and real failure isolation.

All of the above is genuinely category 1/2 from the classification framework: implemented,
and verified as far as a sandbox with no network access can verify anything (see AUDIT.md §5
for what that caveat covers everywhere else in this codebase too).

## 3. The actual gap: there is no multi-participant connection registry

This is the load-bearing piece, and it doesn't exist anywhere in this codebase — not "exists
but unwired," genuinely absent. Worth being direct about, because it changes what "Speaker A
speaks Hindi, Participants B/C/D/E each see a different language" actually requires:

- `routes/ws.py` today handles **one WebSocket connection per meeting** — the owner's own
  view. There's no concept of a second person joining the same `meeting_id`, no participant
  list, no per-connection state beyond the single socket.
- `models/entities.py` has no `Participant`/`MeetingParticipant` table. A `Meeting` has one
  `owner_id`. There's no schema for "who else is in this call and what language do they want."
- Real multi-participant fan-out needs: a connection registry (which sockets are currently in
  meeting X), a per-participant language preference (set via the WS protocol or a join-time
  parameter), and a fan-out step that sends each connected participant the segment translated
  into *their* language instead of one broadcast.

None of that is a translation problem — it's a "this product doesn't have multi-participant
meeting rooms yet" problem, and building it now would be a separate, foundational feature
(join-by-link, participant identity, connection rooms) bolted onto a translation request. That
's the kind of scope-without-a-clear-need this whole project's history has been about avoiding.
**What's real instead:** the single-connection case that exists today can use this pipeline
right now — see §5.

## 4. The other acknowledged gap: no specialized real-time MT model

`LLMTranslationProvider` is real and works, but a true "200+ languages, consistently sub-2s,
many concurrent speakers" system is what self-hosted NLLB-200/SeamlessM4T (GPU model serving:
hosting, batching, autoscaling) or a streaming-optimized commercial API (Google/Azure/DeepL
streaming endpoints, which need a paid account) would provide. Implementing the `Streaming
TranslationProvider` interface for either is a contained, well-scoped follow-up *once* one of
those is actually decided on and has credentials/infra behind it — the interface exists
specifically so that swap doesn't touch the buffer or coordinator.

## 5. What's actually usable today, end to end

The single-connection case: one person (today's only "participant" — the meeting owner) wants
their own live transcript/AI-suggestion text in a language other than what's being spoken.
That's directly buildable on the existing `routes/ws.py` connection with no new infrastructure
— translate the outgoing `AgentResult.suggested_response` (and optionally the transcript line)
through `LiveTranslationCoordinator` before sending it over the one socket that already exists.
Genuinely real, immediately useful, and doesn't require solving §3 first.

## 6. Recommended sequencing

1. (This pass) Buffer + provider interface + LLM-backed provider + coordinator — done, tested.
2. Wire the coordinator into the existing single-connection `routes/ws.py` for "translate my
   own view" — small, real, no new infra.
3. Decide on a real connection-registry / multi-participant design (this is a product
   decision about whether/how people join someone else's meeting at all — bigger than
   translation) before attempting per-participant fan-out.
4. Once a specialized MT provider is chosen and has credentials, implement
   `StreamingTranslationProvider` for it — the buffer/coordinator don't change.
