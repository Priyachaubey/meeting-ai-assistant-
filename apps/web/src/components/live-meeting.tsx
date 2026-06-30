"use client";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { AlertTriangle, Bot, CheckCircle2, Clock, Mic, MicOff, Pause, Play, Send, Square } from "lucide-react";
import { Button } from "@/components/button";
import { api, type AgentResult, type MeetingSummary } from "@/lib/api";
import { resampleAndEncode } from "@/lib/mic-capture";
import { useAuthStore } from "@/store/auth-store";
import { useMeetingStore } from "@/store/meeting-store";

const PREVIEW_TRANSCRIPT = [
  ["Avery", "Can you explain how the RAG layer chooses context for a client call?", "question"],
  ["Mina", "We rank meeting memory, uploaded docs, and account notes, then compress the top passages.", "statement"],
] as const;

// Matches settings.audio_sample_rate_hz on the backend and DeepgramProvider's connection
// params — this is the rate the server actually expects, not a UI preference.
const TARGET_SAMPLE_RATE = 16000;

function formatClock(date: Date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function LiveMeeting({ compact = false }: { compact?: boolean }) {
  const token = useAuthStore((s) => s.token);

  // Public landing page preview (no auth) — clearly labeled as a preview, not real session data.
  if (compact || !token) {
    return (
      <section className={compact ? "p-3 sm:p-4" : "min-h-screen p-4 sm:p-6"}>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-ink/10 bg-white/82 p-3 shadow-soft backdrop-blur-xl">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink/45">Preview</p>
            <h1 className={compact ? "text-base font-semibold" : "text-xl font-semibold"}>Sample meeting workspace</h1>
          </div>
          <Link href="/login">
            <Button className={compact ? "h-9 px-3" : ""}>
              <Play className="h-4 w-4" />
              Sign in to start a live session
            </Button>
          </Link>
        </div>
        <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-soft">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="font-semibold">Transcript</h2>
            <span className="text-xs text-ink/45">example, not live</span>
          </div>
          <div className="space-y-3">
            {PREVIEW_TRANSCRIPT.map(([speaker, text, kind]) => (
              <div key={text} className="rounded-md border border-ink/8 bg-mist p-3">
                <p className="mb-1 text-xs text-ink/50">{speaker}</p>
                <p className={kind === "question" ? "font-medium text-ink" : "text-ink/72"}>{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  return <LiveSession compact={compact} token={token} />;
}

function LiveSession({ compact, token }: { compact: boolean; token: string }) {
  const { lines, start, stop, addLine } = useMeetingStore();
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "connecting" | "live" | "reconnecting" | "ended">("idle");
  const [error, setError] = useState<string | null>(null);
  const [speaker, setSpeaker] = useState("Customer");
  const [draft, setDraft] = useState("");
  const [result, setResult] = useState<AgentResult | null>(null);
  const [summary, setSummary] = useState<MeetingSummary | null>(null);
  const [micActive, setMicActive] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const manualCloseRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Elapsed time since the session started, not absolute epoch time — the Meeting Deep Dive
  // timeline renders timestamp_ms as mm:ss, which only makes sense as "seconds into this
  // session." The backend computes mic-derived timestamps the same way (see ws.py's
  // connection_start) — both input paths have to agree on what timestamp_ms means.
  const sessionStartRef = useRef<number | null>(null);

  // Mic capture plumbing — only ever touched if the user clicks the mic button.
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  useEffect(() => {
    return () => {
      manualCloseRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
      stopMicCapture();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function connectSocket(id: string) {
    const ws = new WebSocket(api.meetingSocketUrl(id, token));
    ws.onopen = () => {
      reconnectAttemptRef.current = 0;
      sessionStartRef.current = Date.now();
      setStatus("live");
      setError(null);
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as AgentResult & { error?: string };
      if (data.error) {
        setError(data.error);
        return;
      }
      setResult(data);
      // Mic-derived lines were never echoed locally (unlike manual entry, which adds its own
      // line immediately in handleSend) — this is the only place they ever reach the UI.
      if (data.speaker === "Microphone" && data.text) {
        addLine({
          id: `mic-${data.timestamp_ms}`,
          speaker: data.speaker,
          text: data.text,
          timestamp: formatClock(new Date((sessionStartRef.current ?? Date.now()) + (data.timestamp_ms ?? 0))),
        });
      }
    };
    ws.onerror = () => setError("WebSocket connection failed — is the API server running?");
    ws.onclose = () => {
      if (manualCloseRef.current) {
        setStatus("ended");
        return;
      }
      // Dropped, not a deliberate Stop — real error recovery: retry with exponential backoff
      // (1s, 2s, 4s, 8s, capped at 10s) rather than either silently giving up or hammering
      // the server. Gives up after 5 attempts (~30s of dropped connection) rather than
      // retrying forever against a server that's genuinely down.
      if (reconnectAttemptRef.current >= 5) {
        setStatus("ended");
        setError("Lost connection and could not reconnect after several attempts.");
        return;
      }
      setStatus("reconnecting");
      const delay = Math.min(1000 * 2 ** reconnectAttemptRef.current, 10_000);
      reconnectAttemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(() => connectSocket(id), delay);
    };
    wsRef.current = ws;
  }

  async function handleStart() {
    setError(null);
    setStatus("connecting");
    manualCloseRef.current = false;
    reconnectAttemptRef.current = 0;
    try {
      const meeting = await api.createMeeting(token, `Meeting ${new Date().toLocaleString()}`);
      setMeetingId(meeting.id);
      connectSocket(meeting.id);
      start();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the meeting.");
      setStatus("idle");
    }
  }

  function handleStop() {
    manualCloseRef.current = true;
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    stopMicCapture();
    wsRef.current?.close();
    setStatus("ended");
    stop();
    if (meetingId) {
      api
        .getMeetingSummary(token, meetingId)
        .then(setSummary)
        .catch((err) => setError(err instanceof Error ? err.message : "Could not load summary."));
    }
  }

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim() || !meetingId || wsRef.current?.readyState !== WebSocket.OPEN) return;
    const text = draft.trim();
    const timestamp_ms = Date.now() - (sessionStartRef.current ?? Date.now());
    wsRef.current.send(JSON.stringify({ speaker, text, timestamp_ms }));
    addLine({ id: `manual-${Date.now()}`, speaker, text, timestamp: formatClock(new Date()) });
    setDraft("");
  }

  async function startMicCapture() {
    setMicError(null);
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      setMicError("Start the session first, then enable the microphone.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      // Browsers commonly ignore a requested sampleRate and use the hardware default
      // (44100/48000Hz) — resampleAndEncode (src/lib/mic-capture.ts) handles the real rate
      // we actually get, not the one we asked for.
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);

      // ScriptProcessorNode is deprecated in favor of AudioWorklet, but still universally
      // supported and far simpler to wire up without serving a separate worklet module file
      // — a deliberate, stated tradeoff, not an oversight. Buffer size 4096 is a reasonable
      // balance between latency and not flooding the socket with tiny frames.
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return;
        const inputData = event.inputBuffer.getChannelData(0);
        const pcm16 = resampleAndEncode(inputData, audioContext.sampleRate, TARGET_SAMPLE_RATE);
        wsRef.current.send(pcm16.buffer);
      };

      source.connect(processor);
      // Connecting to destination is required in some browsers to keep the processing graph
      // alive, even though we never want this played back out loud — there is no separate
      // "mute" needed here because ScriptProcessorNode's output buffer is left untouched
      // (zeros), so nothing audible actually reaches the speakers.
      processor.connect(audioContext.destination);

      setMicActive(true);
    } catch (err) {
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setMicError("Microphone permission denied. Allow microphone access and try again.");
      } else if (err instanceof DOMException && err.name === "NotFoundError") {
        setMicError("No microphone found on this device.");
      } else {
        setMicError(err instanceof Error ? err.message : "Could not start the microphone.");
      }
    }
  }

  function stopMicCapture() {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "end_audio" }));
    }
    processorRef.current?.disconnect();
    processorRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close();
    }
    audioContextRef.current = null;
    setMicActive(false);
  }

  function toggleMic() {
    if (micActive) stopMicCapture();
    else startMicCapture();
  }

  return (
    <section className={compact ? "p-3 sm:p-4" : "min-h-screen p-4 sm:p-6"}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-ink/10 bg-white/82 p-3 shadow-soft backdrop-blur-xl">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink/45">Live Meeting</p>
          <h1 className={compact ? "text-base font-semibold" : "text-xl font-semibold"}>
            {meetingId ? "Session in progress" : "Start a new session"}
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          {status === "idle" && (
            <Button onClick={handleStart}>
              <Play className="h-4 w-4" />
              Start
            </Button>
          )}
          {status === "connecting" && (
            <Button disabled className="bg-white text-ink">
              <Pause className="h-4 w-4" />
              Connecting…
            </Button>
          )}
          {status === "reconnecting" && (
            <Button disabled className="bg-white text-ink">
              <Pause className="h-4 w-4 animate-pulse" />
              Reconnecting…
            </Button>
          )}
          {status === "live" && (
            <Button onClick={toggleMic} className={micActive ? "bg-coral" : ""}>
              {micActive ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              {micActive ? "Stop mic" : "Use microphone"}
            </Button>
          )}
          {(status === "live" || status === "reconnecting") && (
            <Button onClick={handleStop} className="bg-coral">
              <Square className="h-4 w-4" />
              Stop
            </Button>
          )}
          <span
            className={`inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm ${
              status === "live"
                ? "border-jade/30 bg-jade/10 text-ink"
                : status === "reconnecting"
                  ? "border-coral/30 bg-coral/10 text-ink"
                  : "border-ink/15 bg-white text-ink/50"
            }`}
          >
            <Mic className="h-4 w-4" />
            {status === "live"
              ? "AI online"
              : status === "reconnecting"
                ? "Connection dropped — retrying"
                : status === "ended"
                  ? "Session ended"
                  : "Not connected"}
          </span>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-coral/20 bg-coral/10 p-3 text-sm text-coral">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}
      {micError && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-coral/20 bg-coral/10 p-3 text-sm text-coral">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {micError}
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_1.25fr_1fr]">
        <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-soft">
          <h2 className="mb-4 font-semibold">Transcript</h2>
          <div className="mb-3 max-h-[420px] space-y-3 overflow-y-auto">
            {lines.length === 0 && <p className="text-sm text-ink/45">No transcript yet — start the session below.</p>}
            {lines.map((line) => (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                key={line.id}
                className="rounded-md border border-ink/8 bg-mist p-3"
              >
                <div className="mb-1 flex items-center justify-between text-xs text-ink/50">
                  <span>{line.speaker}</span>
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {line.timestamp}
                  </span>
                </div>
                <p className="text-ink/72">{line.text}</p>
              </motion.div>
            ))}
          </div>
          {status === "live" && (
            <form onSubmit={handleSend} className="flex gap-2">
              <input
                value={speaker}
                onChange={(e) => setSpeaker(e.target.value)}
                placeholder="Speaker"
                className="w-24 rounded-md border border-ink/15 px-2 text-sm"
              />
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Type what was said…"
                className="flex-1 rounded-md border border-ink/15 px-2 text-sm"
              />
              <button type="submit" className="grid h-9 w-9 place-items-center rounded-md bg-ink text-white">
                <Send className="h-4 w-4" />
              </button>
            </form>
          )}
          {status === "live" && (
            <p className="mt-2 text-xs text-ink/40">
              Type a line manually, or click "Use microphone" above to stream real audio through
              Deepgram — both feed the same AI pipeline.
            </p>
          )}
        </div>

        <div className="rounded-lg border border-ink/10 bg-ink p-4 text-white shadow-glow">
          <div className="mb-4 flex items-center gap-2">
            <Bot className="h-5 w-5 text-jade" />
            <h2 className="font-semibold">AI Suggestions</h2>
          </div>
          {result?.suggested_response ? (
            <div className="rounded-md bg-white/10 p-4">
              <p className="mb-2 text-sm text-white/58">Suggested response</p>
              <p>{result.suggested_response}</p>
            </div>
          ) : (
            <p className="text-sm text-white/45">No question detected yet.</p>
          )}
          {!!result?.follow_ups.length && (
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {result.follow_ups.map((item) => (
                <p key={item} className="rounded-md border border-white/10 bg-white/5 p-3 text-left text-sm">
                  {item}
                </p>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-soft">
          <h2 className="mb-4 font-semibold">Meeting Intelligence</h2>
          <div className="space-y-4">
            <div>
              <p className="mb-2 text-sm font-medium">Sentiment</p>
              <p className="text-sm text-ink/72">{result?.sentiment ?? "—"}</p>
            </div>
            <div>
              <p className="mb-2 text-sm font-medium">Action Items</p>
              {result?.action_items.length ? (
                result.action_items.map((a) => (
                  <p key={a} className="mb-2 flex gap-2 text-sm text-ink/72">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-jade" />
                    {a}
                  </p>
                ))
              ) : (
                <p className="text-sm text-ink/45">None detected yet.</p>
              )}
            </div>
            {summary && (
              <div className="rounded-md border border-ink/10 bg-mist p-3 text-sm">
                <p className="mb-1 font-medium">Summary</p>
                <p className="text-ink/72">{summary.summary}</p>
                {meetingId && (
                  <Link href={`/meetings/${meetingId}`} className="mt-2 inline-block text-xs text-iris hover:underline">
                    Open full Deep Dive →
                  </Link>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
