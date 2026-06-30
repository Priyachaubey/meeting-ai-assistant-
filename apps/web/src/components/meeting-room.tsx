"use client";
import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Mic, MicOff, Video, VideoOff, Monitor, MonitorOff, PhoneOff,
  MessageSquare, Users, Hand, Circle, CircleDot, Clock,
  Wifi, WifiOff, Grid3X3, LayoutList, X, Send,
  Bot, Sparkles, FileText, CheckCircle2, ListTodo,
  ShieldQuestion, Pin, PenLine,
} from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import { useWebRTCMesh } from "@/hooks/use-webrtc-mesh";
import { useAudioLevel } from "@/hooks/use-audio-level";
import { Whiteboard } from "@/components/whiteboard";
import { resampleAndEncode } from "@/lib/mic-capture";
import { decodeJwtPayload } from "@/lib/jwt-decode";

/* ── Types ──────────────────────────────────────────────────────── */
interface Participant {
  id: string;
  user_id: string;
  name: string;
  isHost: boolean;
  isMuted: boolean;
  isVideoOn: boolean;
  isScreenSharing: boolean;
  isSpeaking: boolean;
  handRaised: boolean;
  connectionQuality: "good" | "fair" | "poor";
  // WS connection_id — see meeting-server's room_state/participant_joined payloads (added
  // alongside the real WebRTC wiring). Used to address signaling messages at the right
  // socket; undefined briefly if a participant record arrives before its connection_id does.
  connectionId?: string;
}

interface TranscriptEntry {
  id: string;
  speaker_id: string;
  speaker_name: string;
  text: string;
  timestamp_ms: number;
  kind: string;
  created_at: string;
}

interface ChatMsg {
  id: string;
  sender_id: string;
  sender_name: string;
  content: string;
  created_at: string;
}

interface AIState {
  summary: string;
  action_items: string[];
  decisions: string[];
  risks: string[];
  follow_ups: string[];
  sentiment: string;
  suggestions: string[];
  questions: { speaker: string; text: string }[];
}

type ViewMode = "gallery" | "speaker";
type SidePanel = "none" | "chat" | "participants" | "ai" | "waiting" | "whiteboard";

/* ── Participant Tile ──────────────────────────────────────────── */
function ParticipantTile({
  participant, large = false, stream, isLocal = false, isPinned = false, onTogglePin,
}: {
  participant: Participant; large?: boolean; stream?: MediaStream | null; isLocal?: boolean;
  isPinned?: boolean; onTogglePin?: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = stream ?? null;
  }, [stream]);

  // Real video track presence, not just the isVideoOn toggle — covers the case where camera
  // permission was denied or no device exists, which used to be visually identical to
  // "camera intentionally off" before this. participant.isVideoOn still gates whether we
  // even try to show video at all (so toggling the camera off doesn't keep showing a frozen
  // last frame from a track that's merely .enabled = false, not actually stopped).
  const hasRealVideo = !!stream && stream.getVideoTracks().length > 0 && participant.isVideoOn;

  // The actual fix for active-speaker highlighting: participant.isSpeaking is real (it comes
  // from server data) but nothing on the backend ever sets it true (confirmed by reading
  // every file in apps/meeting-server — see use-audio-level.ts's docstring) — so it's
  // permanently false in practice. This computes the real thing client-side from the actual
  // audio in `stream`, which every visible tile already has.
  const reallySpeaking = useAudioLevel(stream) || participant.isSpeaking;

  return (
    <div
      onClick={onTogglePin}
      className={cn(
        "relative group rounded-xl overflow-hidden border border-surface bg-ink/90 transition-all",
        large ? "aspect-video" : "aspect-video min-h-[140px]",
        onTogglePin && "cursor-pointer",
        reallySpeaking && "ring-2 ring-[var(--success)]",
        isPinned && "ring-2 ring-brand"
      )}
    >
      {hasRealVideo ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          // Always mute the local preview — otherwise you hear your own mic looped back
          // through your own speakers, the classic instant-feedback-loop WebRTC bug. Remote
          // participants' audio plays normally (muted only applies to this <video> element,
          // which is just the video+audio sink for one specific stream).
          muted={isLocal}
          className="absolute inset-0 h-full w-full object-cover"
        />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-ink to-ink/80">
          <div className={cn(
            "flex items-center justify-center rounded-full font-bold",
            participant.isVideoOn ? "h-16 w-16 bg-brand/20 text-2xl text-brand" : "h-20 w-20 bg-surface text-3xl text-ink-secondary"
          )}>
            {participant.name.charAt(0)}
          </div>
        </div>
      )}
      {isPinned && (
        <div className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-brand/90 px-2 py-0.5 text-[10px] font-medium text-white">
          <Pin className="h-2.5 w-2.5" /> Pinned
        </div>
      )}
      <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between bg-gradient-to-t from-black/60 to-transparent px-3 py-2">
        <span className="text-sm font-medium text-white truncate max-w-[120px]">
          {participant.name}
          {participant.isHost && <span className="ml-1.5 text-xs text-white/50">(Host)</span>}
        </span>
        <div className="flex items-center gap-1.5">
          {participant.handRaised && <Hand className="h-3.5 w-3.5 text-[var(--warning)]" />}
          {participant.isMuted ? <MicOff className="h-3.5 w-3.5 text-[var(--danger)]" /> : <Mic className="h-3.5 w-3.5 text-white/70" />}
          {participant.connectionQuality === "poor" && <WifiOff className="h-3.5 w-3.5 text-[var(--danger)]" />}
          {participant.connectionQuality === "fair" && <Wifi className="h-3.5 w-3.5 text-[var(--warning)]" />}
        </div>
      </div>
      {reallySpeaking && <div className="absolute inset-0 rounded-xl ring-2 ring-[var(--success)] ring-inset pointer-events-none" />}
    </div>
  );
}

/* ── AI Panel (real-time) ──────────────────────────────────────── */
function AIPanel({
  aiState, transcript, roomId, token, onRefresh,
}: {
  aiState: AIState | null;
  transcript: TranscriptEntry[];
  roomId: string;
  token: string;
  onRefresh: () => void;
}) {
  const [activeTab, setActiveTab] = useState<"transcript" | "summary" | "actions" | "chat">("transcript");
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<{ q: string; a: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  const handleAskAI = async () => {
    if (!chatInput.trim()) return;
    const q = chatInput;
    setChatInput("");
    setLoading(true);
    try {
      const res = await api.askMeetingAI(token, roomId, q);
      setChatHistory(prev => [...prev, { q, a: res.answer }]);
    } catch {
      setChatHistory(prev => [...prev, { q, a: "Unable to get a response. The AI service may be unavailable." }]);
    }
    setLoading(false);
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      await api.triggerAIAnalysis(token, roomId);
      onRefresh();
    } catch { /* ignore */ }
    setAnalyzing(false);
  };

  const tabs = [
    { id: "transcript" as const, label: "Transcript", icon: FileText },
    { id: "summary" as const, label: "Summary", icon: Sparkles },
    { id: "actions" as const, label: "Actions", icon: ListTodo },
    { id: "chat" as const, label: "AI Chat", icon: Bot },
  ];

  return (
    <div className="flex h-full flex-col border-l border-surface bg-elevated">
      <div className="flex border-b border-surface">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setActiveTab(id)} className={cn(
            "flex flex-1 items-center justify-center gap-1.5 px-2 py-3 text-xs font-medium transition-colors",
            activeTab === id ? "text-brand border-b-2 border-brand" : "text-ink-tertiary hover:text-ink-secondary"
          )}>
            <Icon className="h-3.5 w-3.5" />
            <span className="hidden xl:inline">{label}</span>
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "transcript" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs text-ink-tertiary uppercase tracking-wider font-medium">Live Transcript</p>
              <span className="text-xs text-ink-tertiary">{transcript.length} entries</span>
            </div>
            {transcript.length === 0 && <p className="text-sm text-ink-tertiary">No transcript yet. Start speaking or type manually.</p>}
            {transcript.slice(-30).map((entry) => (
              <div key={entry.id} className={cn("rounded-lg p-3", entry.kind === "question" ? "border border-brand/20 bg-brand/5" : "bg-surface-hover")}>
                <p className="text-xs text-ink-tertiary mb-1">
                  {entry.speaker_name} &middot; {Math.floor(entry.timestamp_ms / 60000)}:{String(Math.floor((entry.timestamp_ms % 60000) / 1000)).padStart(2, "0")}
                  {entry.kind === "question" && <span className="ml-2 text-brand">Question</span>}
                </p>
                <p className="text-sm text-ink-secondary">{entry.text}</p>
              </div>
            ))}
          </div>
        )}
        {activeTab === "summary" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-xs text-ink-tertiary uppercase tracking-wider font-medium">Meeting Intelligence</p>
              <Button size="sm" variant="secondary" onClick={handleAnalyze} loading={analyzing}>
                Analyze
              </Button>
            </div>
            {aiState?.summary ? (
              <div className="rounded-lg bg-surface-hover p-4">
                <p className="text-sm text-ink-secondary leading-relaxed whitespace-pre-wrap">{aiState.summary}</p>
              </div>
            ) : (
              <p className="text-sm text-ink-tertiary">Click Analyze to generate a summary.</p>
            )}
            {aiState?.sentiment && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-ink-tertiary">Sentiment:</span>
                <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full",
                  aiState.sentiment === "positive" ? "bg-[var(--success-bg)] text-[var(--success)]" :
                  aiState.sentiment === "negative" ? "bg-[var(--danger-bg)] text-[var(--danger)]" :
                  "bg-surface-hover text-ink-secondary"
                )}>{aiState.sentiment}</span>
              </div>
            )}
            {aiState?.decisions && aiState.decisions.length > 0 && (
              <div>
                <p className="text-xs font-medium mb-2 flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-[var(--success)]" /> Decisions
                </p>
                <ul className="space-y-1.5 text-sm text-ink-secondary">
                  {aiState.decisions.map((d, i) => <li key={i} className="flex gap-2"><span className="text-brand">{i + 1}.</span> {d}</li>)}
                </ul>
              </div>
            )}
            {aiState?.risks && aiState.risks.length > 0 && (
              <div>
                <p className="text-xs font-medium mb-2 text-[var(--danger)]">Risks</p>
                <ul className="space-y-1.5 text-sm text-ink-secondary">
                  {aiState.risks.map((r, i) => <li key={i} className="flex gap-2"><span className="text-[var(--danger)]">{i + 1}.</span> {r}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}
        {activeTab === "actions" && (
          <div className="space-y-4">
            <p className="text-xs text-ink-tertiary uppercase tracking-wider font-medium">Action Items & Follow-ups</p>
            {aiState?.action_items && aiState.action_items.length > 0 ? (
              aiState.action_items.map((item, i) => (
                <div key={i} className="flex items-start gap-3 rounded-lg bg-surface-hover p-3">
                  <div className="mt-0.5 h-4 w-4 rounded border-2 border-ink-placeholder flex items-center justify-center shrink-0" />
                  <p className="text-sm text-ink">{item}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-ink-tertiary">No action items detected yet.</p>
            )}
            {aiState?.follow_ups && aiState.follow_ups.length > 0 && (
              <div>
                <p className="text-xs font-medium mb-2 text-ink-secondary">Follow-ups</p>
                {aiState.follow_ups.map((item, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-lg bg-surface-hover p-3 mb-2">
                    <div className="mt-0.5 h-4 w-4 rounded border-2 border-brand/30 flex items-center justify-center shrink-0" />
                    <p className="text-sm text-ink-secondary">{item}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {activeTab === "chat" && (
          <div className="flex flex-col h-full">
            <p className="text-xs text-ink-tertiary uppercase tracking-wider font-medium mb-3">Ask AI about this meeting</p>
            <div className="flex-1 space-y-3 mb-4 overflow-y-auto">
              {chatHistory.map((item, i) => (
                <div key={i}>
                  <div className="rounded-lg bg-surface-hover p-3">
                    <p className="text-xs text-ink-tertiary mb-1">You</p>
                    <p className="text-sm text-ink">{item.q}</p>
                  </div>
                  <div className="rounded-lg border border-brand/20 bg-brand/5 p-3 mt-2">
                    <p className="text-xs text-brand mb-1 flex items-center gap-1"><Bot className="h-3 w-3" /> ConvoPilot AI</p>
                    <p className="text-sm text-ink-secondary leading-relaxed whitespace-pre-wrap">{item.a}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAskAI()}
                placeholder="Ask about the meeting..."
                className="flex-1 rounded-lg border border-surface bg-surface-hover px-3 py-2 text-sm outline-none focus:border-brand placeholder:text-ink-placeholder"
              />
              <button onClick={handleAskAI} disabled={loading} className="grid h-9 w-9 place-items-center rounded-lg gradient-brand text-white disabled:opacity-50">
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Chat Panel (real-time) ────────────────────────────────────── */
function ChatPanel({
  messages, roomId, token, onSend,
}: {
  messages: ChatMsg[];
  roomId: string;
  token: string;
  onSend: (content: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!draft.trim()) return;
    onSend(draft);
    setDraft("");
  };

  return (
    <div className="flex h-full flex-col border-l border-surface bg-elevated">
      <div className="flex items-center justify-between border-b border-surface px-4 py-3">
        <h3 className="text-sm font-semibold">Meeting Chat</h3>
        <span className="text-xs text-ink-tertiary">{messages.length} messages</span>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && <p className="text-sm text-ink-tertiary text-center py-8">No messages yet</p>}
        {messages.map((msg) => (
          <div key={msg.id} className="animate-fade-in">
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-medium">{msg.sender_name}</span>
              <span className="text-xs text-ink-tertiary">{new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
            </div>
            <p className="mt-0.5 text-sm text-ink-secondary">{msg.content}</p>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="border-t border-surface p-3">
        <div className="flex items-center gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type a message..."
            className="flex-1 rounded-lg border border-surface bg-surface-hover px-3 py-2 text-sm outline-none focus:border-brand placeholder:text-ink-placeholder"
          />
          <button onClick={handleSend} className="grid h-9 w-9 place-items-center rounded-lg gradient-brand text-white">
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Participants Panel ────────────────────────────────────────── */
function ParticipantsPanel({ participants }: { participants: Participant[] }) {
  return (
    <div className="flex h-full flex-col border-l border-surface bg-elevated">
      <div className="flex items-center justify-between border-b border-surface px-4 py-3">
        <h3 className="text-sm font-semibold">Participants</h3>
        <span className="text-xs text-ink-tertiary">{participants.length} in room</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {participants.map((p) => (
          <div key={p.id} className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-surface-hover transition-colors">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand/10 text-sm font-medium text-brand">{p.name.charAt(0)}</div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{p.name}{p.isHost && <span className="ml-1.5 text-xs text-ink-tertiary">(Host)</span>}</p>
            </div>
            <div className="flex items-center gap-1.5">
              {p.handRaised && <Hand className="h-3.5 w-3.5 text-[var(--warning)]" />}
              {p.isMuted ? <MicOff className="h-3.5 w-3.5 text-ink-tertiary" /> : <Mic className="h-3.5 w-3.5 text-[var(--success)]" />}
              {p.isVideoOn ? <Video className="h-3.5 w-3.5 text-[var(--success)]" /> : <VideoOff className="h-3.5 w-3.5 text-ink-tertiary" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Host Waiting Room Panel ───────────────────────────────────── */
// Backend (admit/reject/list) already existed and was already correct (§24's audit) — this
// is the first frontend UI for any of it. Re-fetches whenever `refreshSignal` changes
// (driven by the `waiting_list_changed` WS broadcast added alongside this) rather than
// polling on its own timer, since a host viewing this panel is already WS-connected.
function HostWaitingPanel({
  token, roomId, refreshSignal,
}: { token: string; roomId: string; refreshSignal: number }) {
  const [waiting, setWaiting] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await api.getWaitingList(token, roomId);
      setWaiting(res.waiting);
    } catch { /* transient — next refreshSignal or interval tick retries */ }
    setLoading(false);
  }, [token, roomId]);

  useEffect(() => { refresh(); }, [refresh, refreshSignal]);
  // Belt-and-suspenders polling on top of the WS-driven refresh above — a host might open
  // this panel after someone's already been sitting in the waiting room for a while, with
  // no fresh `waiting_list_changed` event about to fire to trigger a refetch.
  useEffect(() => {
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  async function handleAdmit(participantId: string) {
    setBusyId(participantId);
    try {
      await api.admitFromWaiting(token, roomId, participantId);
      setWaiting(prev => prev.filter(p => p.id !== participantId));
    } catch { /* the panel's next refresh (WS-driven or 5s poll) will reconcile either way */ }
    setBusyId(null);
  }

  async function handleReject(participantId: string) {
    setBusyId(participantId);
    try {
      await api.rejectFromWaiting(token, roomId, participantId);
      setWaiting(prev => prev.filter(p => p.id !== participantId));
    } catch { /* same reasoning as handleAdmit */ }
    setBusyId(null);
  }

  return (
    <div className="flex h-full flex-col border-l border-surface bg-elevated">
      <div className="flex items-center justify-between border-b border-surface px-4 py-3">
        <h3 className="text-sm font-semibold">Waiting room</h3>
        <span className="text-xs text-ink-tertiary">{waiting.length} waiting</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {loading ? (
          <p className="px-1 py-4 text-center text-sm text-ink-tertiary">Loading…</p>
        ) : waiting.length === 0 ? (
          <p className="px-1 py-4 text-center text-sm text-ink-tertiary">No one is waiting right now.</p>
        ) : (
          waiting.map((p) => {
            const id = p.id as string;
            const name = (p.display_name as string) || "Guest";
            return (
              <div key={id} className="flex items-center gap-3 rounded-lg border border-surface px-3 py-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand/10 text-sm font-medium text-brand">
                  {name.charAt(0)}
                </div>
                <p className="flex-1 truncate text-sm font-medium">{name}</p>
                <button
                  onClick={() => handleAdmit(id)}
                  disabled={busyId === id}
                  className="rounded-md bg-jade px-2.5 py-1.5 text-xs font-medium text-white transition hover:brightness-110 disabled:opacity-50"
                >
                  Admit
                </button>
                <button
                  onClick={() => handleReject(id)}
                  disabled={busyId === id}
                  className="rounded-md border border-surface px-2.5 py-1.5 text-xs font-medium text-ink-secondary transition hover:bg-surface-hover disabled:opacity-50"
                >
                  Deny
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

/* ── Host Controls Menu ────────────────────────────────────────── */
// Uses apps/meeting-server's existing /host/action endpoint exactly as already built (lock,
// unlock, mute_all, remove_participant, end_meeting — see meetings.py's host_action route,
// confirmed by reading it directly before building this, not assumed). Only rendered for the
// actual host — see its call site below.
function HostControlsMenu({
  token, roomId, isLocked, onLockChange, onEndMeeting,
}: { token: string; roomId: string; isLocked: boolean; onLockChange: (locked: boolean) => void; onEndMeeting: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function run(action: string, after?: () => void) {
    setBusy(true);
    try {
      await api.hostAction(token, roomId, action);
      after?.();
    } catch { /* the action's own button stays visible to retry — no silent state change */ }
    setBusy(false);
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="grid h-10 w-10 place-items-center rounded-full bg-surface-hover text-ink transition-all hover:bg-surface-active"
        title="Host controls"
      >
        <ShieldQuestion className="h-5 w-5" />
      </button>
      {open && (
        <div className="absolute bottom-full right-0 mb-2 w-56 rounded-xl border border-surface bg-elevated p-1.5 shadow-xl animate-scale-in">
          <button disabled={busy} onClick={() => run("mute_all")} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition hover:bg-surface-hover disabled:opacity-50">
            <MicOff className="h-4 w-4 text-ink-tertiary" /> Mute everyone
          </button>
          <button disabled={busy} onClick={() => run(isLocked ? "unlock" : "lock", () => onLockChange(!isLocked))} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition hover:bg-surface-hover disabled:opacity-50">
            <ShieldQuestion className="h-4 w-4 text-ink-tertiary" /> {isLocked ? "Unlock meeting" : "Lock meeting"}
          </button>
          <div className="my-1 h-px bg-surface-border" />
          <button
            disabled={busy}
            onClick={() => run("end_meeting", onEndMeeting)}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-[var(--danger)] transition hover:bg-[var(--danger)]/10 disabled:opacity-50"
          >
            <PhoneOff className="h-4 w-4" /> End meeting for everyone
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Emoji Reactions ───────────────────────────────────────────── */
// Backend already has a fully working `emoji` WS message type (broadcasts via
// SignallingMessage.emoji_reaction) — this was simply never called from anywhere in the
// frontend, and there was no receiving UI for it either (see FloatingReactions below).
const REACTION_EMOJIS = ["👍", "👏", "❤️", "😂", "🎉", "🔥"] as const;

function EmojiPicker({ onSend }: { onSend: (emoji: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="grid h-10 w-10 place-items-center rounded-full bg-surface-hover text-ink transition-all hover:bg-surface-active"
      >
        <span className="text-lg leading-none">😀</span>
      </button>
      {open && (
        <div className="absolute bottom-full left-1/2 mb-2 flex -translate-x-1/2 gap-1 rounded-full border border-surface bg-elevated p-1.5 shadow-xl animate-scale-in">
          {REACTION_EMOJIS.map((emoji) => (
            <button
              key={emoji}
              onClick={() => { onSend(emoji); setOpen(false); }}
              className="grid h-9 w-9 place-items-center rounded-full text-lg transition hover:bg-surface-hover hover:scale-110"
            >
              {emoji}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

interface FloatingReaction {
  id: string;
  emoji: string;
  // Roughly which side it floats up from — purely cosmetic variety, not tied to any real
  // participant position (the grid is dynamic/responsive, so there's no stable on-screen
  // coordinate for a given participant to anchor a reaction to without a lot more layout
  // plumbing — random horizontal placement reads as "a reaction happened" just as well for
  // what this needs to communicate, without that complexity).
  leftPercent: number;
}

function FloatingReactions({ reactions }: { reactions: FloatingReaction[] }) {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {reactions.map((r) => (
        <span
          key={r.id}
          className="absolute bottom-20 animate-[float-up_2.5s_ease-out_forwards] text-3xl"
          style={{ left: `${r.leftPercent}%` }}
        >
          {r.emoji}
        </span>
      ))}
    </div>
  );
}

/* ── Meeting Toolbar ───────────────────────────────────────────── */
function MeetingToolbar(props: {
  isMuted: boolean; setIsMuted: (v: boolean) => void;
  isVideoOn: boolean; setIsVideoOn: (v: boolean) => void;
  isScreenSharing: boolean; setIsScreenSharing: (v: boolean) => void;
  isRecording: boolean; isRecordingPaused: boolean; recordingSeconds: number;
  onStartRecording: () => void; onStopRecording: () => void;
  onPauseRecording: () => void; onResumeRecording: () => void;
  handRaised: boolean; setHandRaised: (v: boolean) => void;
  onSendEmoji: (emoji: string) => void;
  sidePanel: SidePanel; setSidePanel: (v: SidePanel) => void;
  isHost: boolean; token: string; roomId: string; isLocked: boolean;
  onLockChange: (locked: boolean) => void; onEndMeeting: () => void;
  viewMode: ViewMode; setViewMode: (v: ViewMode) => void;
  elapsed: string;
  onLeave: () => void;
}) {
  const [showMore, setShowMore] = useState(false);

  return (
    <div className="flex items-center justify-between border-t border-surface bg-elevated/95 backdrop-blur-xl px-4 py-2.5">
      <div className="hidden sm:flex items-center gap-3">
        <div className="flex items-center gap-2">
          <CircleDot className={cn("h-3 w-3", props.isRecording ? "text-[var(--danger)] animate-pulse" : "text-ink-tertiary")} />
          <span className="text-xs text-ink-tertiary"><Clock className="inline h-3 w-3 mr-1" />{props.elapsed}</span>
        </div>
        <div className="h-4 w-px bg-surface-border" />
        <button onClick={() => props.setViewMode(props.viewMode === "gallery" ? "speaker" : "gallery")} className="flex items-center gap-1.5 text-xs text-ink-tertiary hover:text-ink-secondary">
          {props.viewMode === "gallery" ? <Grid3X3 className="h-3.5 w-3.5" /> : <LayoutList className="h-3.5 w-3.5" />}
          {props.viewMode === "gallery" ? "Gallery" : "Speaker"}
        </button>
      </div>
      <div className="flex items-center gap-1.5 sm:gap-2">
        <button onClick={() => props.setIsMuted(!props.isMuted)} className={cn("grid h-10 w-10 place-items-center rounded-full transition-all", props.isMuted ? "bg-[var(--danger)] text-white" : "bg-surface-hover text-ink hover:bg-surface-active")}>
          {props.isMuted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
        </button>
        <button onClick={() => props.setIsVideoOn(!props.isVideoOn)} className={cn("grid h-10 w-10 place-items-center rounded-full transition-all", !props.isVideoOn ? "bg-[var(--danger)] text-white" : "bg-surface-hover text-ink hover:bg-surface-active")}>
          {props.isVideoOn ? <Video className="h-5 w-5" /> : <VideoOff className="h-5 w-5" />}
        </button>
        <button onClick={() => props.setIsScreenSharing(!props.isScreenSharing)} className={cn("grid h-10 w-10 place-items-center rounded-full transition-all", props.isScreenSharing ? "bg-brand text-white" : "bg-surface-hover text-ink hover:bg-surface-active")}>
          {props.isScreenSharing ? <MonitorOff className="h-5 w-5" /> : <Monitor className="h-5 w-5" />}
        </button>
        <div className="hidden sm:block h-8 w-px bg-surface-border mx-1" />
        <button onClick={() => props.setHandRaised(!props.handRaised)} className={cn("grid h-10 w-10 place-items-center rounded-full transition-all", props.handRaised ? "bg-[var(--warning)] text-white" : "bg-surface-hover text-ink hover:bg-surface-active")}>
          <Hand className="h-5 w-5" />
        </button>
        <EmojiPicker onSend={props.onSendEmoji} />
        {props.isRecording ? (
          <div className="flex items-center gap-1 rounded-full bg-[var(--danger)]/10 pl-1 pr-2">
            <button
              onClick={props.isRecordingPaused ? props.onResumeRecording : props.onPauseRecording}
              className="grid h-8 w-8 place-items-center rounded-full text-[var(--danger)] transition hover:bg-[var(--danger)]/15"
              title={props.isRecordingPaused ? "Resume recording" : "Pause recording"}
            >
              {props.isRecordingPaused ? <Circle className="h-4 w-4" /> : <span className="flex gap-0.5"><span className="h-3 w-1 rounded-sm bg-current" /><span className="h-3 w-1 rounded-sm bg-current" /></span>}
            </button>
            <span className="font-mono text-xs text-[var(--danger)]">
              {String(Math.floor(props.recordingSeconds / 60)).padStart(2, "0")}:{String(props.recordingSeconds % 60).padStart(2, "0")}
            </span>
            <button onClick={props.onStopRecording} className="grid h-8 w-8 place-items-center rounded-full text-[var(--danger)] transition hover:bg-[var(--danger)]/15" title="Stop recording">
              <div className="h-2.5 w-2.5 rounded-sm bg-current" />
            </button>
          </div>
        ) : (
          <button onClick={props.onStartRecording} className="grid h-10 w-10 place-items-center rounded-full bg-surface-hover text-ink transition-all hover:bg-surface-active" title="Start recording">
            <Circle className="h-5 w-5" />
          </button>
        )}
        <div className="hidden sm:block h-8 w-px bg-surface-border mx-1" />
        <button onClick={props.onLeave} className="flex h-10 items-center gap-2 rounded-full bg-[var(--danger)] px-5 text-sm font-medium text-white hover:brightness-110 transition-all">
          <PhoneOff className="h-4 w-4" /><span className="hidden sm:inline">Leave</span>
        </button>
      </div>
      <div className="hidden sm:flex items-center gap-1">
        <button onClick={() => props.setSidePanel(props.sidePanel === "chat" ? "none" : "chat")} className={cn("grid h-10 w-10 place-items-center rounded-full transition-all", props.sidePanel === "chat" ? "bg-brand text-white" : "bg-surface-hover text-ink hover:bg-surface-active")}>
          <MessageSquare className="h-5 w-5" />
        </button>
        <button onClick={() => props.setSidePanel(props.sidePanel === "participants" ? "none" : "participants")} className={cn("grid h-10 w-10 place-items-center rounded-full transition-all", props.sidePanel === "participants" ? "bg-brand text-white" : "bg-surface-hover text-ink hover:bg-surface-active")}>
          <Users className="h-5 w-5" />
        </button>
        <button onClick={() => props.setSidePanel(props.sidePanel === "ai" ? "none" : "ai")} className={cn("grid h-10 w-10 place-items-center rounded-full transition-all", props.sidePanel === "ai" ? "bg-brand text-white" : "bg-surface-hover text-ink hover:bg-surface-active")}>
          <Bot className="h-5 w-5" />
        </button>
        <button onClick={() => props.setSidePanel(props.sidePanel === "whiteboard" ? "none" : "whiteboard")} className={cn("grid h-10 w-10 place-items-center rounded-full transition-all", props.sidePanel === "whiteboard" ? "bg-brand text-white" : "bg-surface-hover text-ink hover:bg-surface-active")} title="Whiteboard">
          <PenLine className="h-5 w-5" />
        </button>
        {props.isHost && (
          <>
            <button onClick={() => props.setSidePanel(props.sidePanel === "waiting" ? "none" : "waiting")} className={cn("grid h-10 w-10 place-items-center rounded-full transition-all", props.sidePanel === "waiting" ? "bg-brand text-white" : "bg-surface-hover text-ink hover:bg-surface-active")} title="Waiting room">
              <Clock className="h-5 w-5" />
            </button>
            <HostControlsMenu token={props.token} roomId={props.roomId} isLocked={props.isLocked} onLockChange={props.onLockChange} onEndMeeting={props.onEndMeeting} />
          </>
        )}
      </div>
    </div>
  );
}

/* ── Create/Join Meeting Modal ─────────────────────────────────── */
function CreateMeetingModal({ token, onClose, onStart }: { token: string; onClose: () => void; onStart: (roomId: string, title: string, state?: string) => void }) {
  const [title, setTitle] = useState("");
  const [tab, setTab] = useState<"create" | "join">("create");
  const [joinCode, setJoinCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleCreate = async () => {
    setLoading(true);
    setError("");
    try {
      const room = await api.createMeetingRoom(token, { title: title || "New Meeting" });
      onStart(room.id, room.title);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create meeting");
    }
    setLoading(false);
  };

  const handleJoin = async () => {
    if (!joinCode.trim()) return;
    setLoading(true);
    setError("");
    try {
      const roomId = joinCode.includes("/") ? joinCode.split("/").pop()! : joinCode;
      // The actual fix: previously this ignored the response's `state` field entirely and
      // always proceeded straight into the meeting room — for a waiting_room=true meeting,
      // that meant connecting a WebSocket the backend's access-control fix (see meetings.py)
      // would immediately reject with no graceful "you're waiting" UI, just a confusing
      // instant disconnect. Reading `state` here is what makes the WaitingRoomScreen below
      // actually reachable from this entry point, not just from a direct /meeting/{id} link.
      const res = await api.joinMeetingRoom(token, roomId, "User");
      onStart(roomId, "Joined Meeting", res.state);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to join meeting");
    }
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <div className="relative w-full max-w-md animate-scale-in rounded-2xl border border-surface bg-elevated shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-surface px-6 py-4">
          <h2 className="text-lg font-semibold">Meeting Room</h2>
          <button onClick={onClose} className="grid h-8 w-8 place-items-center rounded-lg hover:bg-surface-hover"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex border-b border-surface">
          <button onClick={() => setTab("create")} className={cn("flex-1 py-3 text-sm font-medium transition-colors border-b-2", tab === "create" ? "text-brand border-brand" : "text-ink-tertiary border-transparent")}>New Meeting</button>
          <button onClick={() => setTab("join")} className={cn("flex-1 py-3 text-sm font-medium transition-colors border-b-2", tab === "join" ? "text-brand border-brand" : "text-ink-tertiary border-transparent")}>Join Meeting</button>
        </div>
        <div className="p-6">
          {error && <p className="mb-3 text-sm text-[var(--danger)]">{error}</p>}
          {tab === "create" ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">Meeting title</label>
                <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Weekly standup" className="w-full rounded-lg border border-surface bg-surface-hover px-3 py-2.5 text-sm outline-none focus:border-brand placeholder:text-ink-placeholder" />
              </div>
              <Button className="w-full" onClick={handleCreate} loading={loading}>Start Meeting</Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">Meeting code or link</label>
                <input value={joinCode} onChange={(e) => setJoinCode(e.target.value)} placeholder="meeting-room-uuid" className="w-full rounded-lg border border-surface bg-surface-hover px-3 py-2.5 text-sm outline-none focus:border-brand placeholder:text-ink-placeholder" />
              </div>
              <Button className="w-full" onClick={handleJoin} loading={loading}>Join Meeting</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Main Meeting Room ─────────────────────────────────────────── */
// `initialRoomId`: when set (by the dedicated /meeting/[meetingId] route — see that page's
// comment for why this exists), skips the create/join modal entirely and joins that room
// directly. Without it (e.g. /rooms), behaves exactly as before — modal-first, no prop
// needed, fully backward compatible.
export function MeetingRoom({ initialRoomId }: { initialRoomId?: string } = {}) {
  const token = useAuthStore((s) => s.token) || "";
  const router = useRouter();
  const [inMeeting, setInMeeting] = useState(false);
  const [showModal, setShowModal] = useState(!initialRoomId);
  const [autoJoinError, setAutoJoinError] = useState<string | null>(null);
  const [isWaiting, setIsWaiting] = useState(false);
  const myUserId = useMemo(() => (token ? (decodeJwtPayload(token)?.sub as string | undefined) : undefined), [token]);

  // Detects admission by polling rather than holding a WebSocket open across the
  // waiting->admitted transition — see the backend's matching comment (apps/meeting-server's
  // WS handler) for why that's the simpler, more robust choice here. 3s is frequent enough
  // to feel responsive without hammering the endpoint for what's normally a short wait.
 
  const [roomId, setRoomId] = useState(initialRoomId || "");
  const [roomTitle, setRoomTitle] = useState("");
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOn, setIsVideoOn] = useState(true);
  const [isLocked, setIsLocked] = useState(false);
  const [handRaised, setHandRaisedState] = useState(false);
  const [floatingReactions, setFloatingReactions] = useState<FloatingReaction[]>([]);
  const [waitingListVersion, setWaitingListVersion] = useState(0);
  const [whiteboardStrokes, setWhiteboardStrokes] = useState<Record<string, unknown>[]>([]);

useEffect(() => {
  if (!isWaiting || !roomId || !token || !myUserId) return;

  let cancelled = false;

  const interval = setInterval(async () => {
    try {
      const res = await api.getMeetingRoom(token, roomId);
      const me = res.participants.find(
        (p) => (p as Record<string, unknown>).user_id === myUserId
      );

      if (!cancelled && me && (me as Record<string, unknown>).state === "in_room") {
        setIsWaiting(false);
        setInMeeting(true);
      }
    } catch {}

  }, 3000);

  return () => {
    cancelled = true;
    clearInterval(interval);
  };
}, [isWaiting, roomId, token, myUserId]);
  const sendWhiteboardDraw = useCallback((stroke: { tool: string; points: number[]; color: string; width: number; text?: string | null }) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "whiteboard_draw", ...stroke }));
    }
  }, []);
  const sendWhiteboardUndo = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "whiteboard_undo" }));
  }, []);
  const sendWhiteboardRedo = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "whiteboard_redo" }));
  }, []);
  const sendWhiteboardClear = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "whiteboard_clear" }));
  }, []);

  // The actual fix: previously this only flipped local UI state. The backend's `hand` WS
  // handler (apps/meeting-server/app/api/routes/meetings.py) already persists this on the
  // Participant model and broadcasts `hand_raised` to everyone else — already-existing,
  // already-correct code that nothing ever called.
  const setHandRaised = useCallback((raised: boolean) => {
    setHandRaisedState(raised);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "hand", raised }));
    }
  }, []);

  const sendEmoji = useCallback((emoji: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "emoji", emoji }));
    }
  }, []);
  const [viewMode, setViewMode] = useState<ViewMode>("gallery");
  const [pinnedParticipantId, setPinnedParticipantId] = useState<string | null>(null);
  const [sidePanel, setSidePanel] = useState<SidePanel>("none");
  const [participants, setParticipants] = useState<Participant[]>([]);
  const amIHost = useMemo(() => participants.some(p => p.user_id === myUserId && p.isHost), [participants, myUserId]);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [aiState, setAiState] = useState<AIState | null>(null);
  const [elapsed, setElapsed] = useState("00:00");
  const [wsConnected, setWsConnected] = useState(false);
  const [myConnectionId, setMyConnectionId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const startTimeRef = useRef<number>(0);

  // Auto-join when arriving via /meeting/{meetingId} — this is the actual fix for "no
  // dedicated route, everything is a popup over a static page": that page passes its URL
  // param in as initialRoomId, and this effect joins it directly instead of showing the
  // create/join modal. A failed join (bad ID, room ended, no longer a member) surfaces an
  // inline error with a way back to the picker, rather than silently sitting on a blank
  // screen or throwing an unhandled rejection.
  useEffect(() => {
    if (!initialRoomId || !token || inMeeting || isWaiting) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.joinMeetingRoom(token, initialRoomId, "User");
        if (cancelled) return;
        if (res.state === "in_waiting_room") {
          setIsWaiting(true);
          return;
        }
        setRoomTitle("Meeting");
        setInMeeting(true);
      } catch (err) {
        if (cancelled) return;
        setAutoJoinError(err instanceof Error ? err.message : "Failed to join meeting");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initialRoomId, token, inMeeting, isWaiting]);

  // Timer
  useEffect(() => {
    if (!inMeeting) return;
    startTimeRef.current = Date.now();
    const interval = setInterval(() => {
      const diff = Math.floor((Date.now() - startTimeRef.current) / 1000);
      const m = Math.floor(diff / 60);
      const s = diff % 60;
      setElapsed(`${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`);
    }, 1000);
    return () => clearInterval(interval);
  }, [inMeeting]);

  // WebSocket connection
  useEffect(() => {
    if (!roomId || !token) return;
    const wsUrl = api.meetingServerSocketUrl(roomId, token);
    let ws: WebSocket;
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let reconnectAttempts = 0;
    let cancelled = false;

    async function connect() {
      // Re-join before reconnect attempts (reconnectAttempts > 0) — NOT before the very
      // first connection, which would create a duplicate participant record: the modal's
      // handleJoin / the auto-join effect already call api.joinMeetingRoom() once before
      // this effect even runs, and add_participant() has no dedup-by-user_id (confirmed by
      // reading participants/manager.py directly), so joining twice for the same user
      // produces two separate participant entries, not one. Re-joining only matters once
      // we've actually disconnected — found necessary alongside a real backend security fix
      // (apps/meeting-server's WS handler now requires an actual participant record to
      // exist, and that same backend already removes the record on every disconnect,
      // including a brief network blip) — without this, the auto-reconnect logic below
      // would now correctly get rejected by the fixed backend instead of silently exploiting
      // the hole it used to fall through.
      if (reconnectAttempts > 0) {
        try {
          await api.joinMeetingRoom(token, roomId, "User");
        } catch {
          // If re-join itself fails (room ended, removed by host, etc.) there's nothing
          // useful a WS connection attempt could do anyway — let the close handler's own
          // attempt counter naturally stop retrying rather than surfacing a separate error.
        }
        if (cancelled) return;
      }

      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;
        ws.onopen = () => {
          setWsConnected(true);
          reconnectAttempts = 0;
        };
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            handleWSMessage(data);
          } catch { /* ignore parse errors */ }
        };
        ws.onclose = () => {
          setWsConnected(false);
          if (reconnectAttempts < 5 && inMeeting) {
            reconnectAttempts++;
            reconnectTimeout = setTimeout(connect, Math.min(1000 * 2 ** reconnectAttempts, 10000));
          }
        };
        ws.onerror = () => { /* handled by onclose */ };
      } catch { /* connection failed */ }
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(reconnectTimeout);
      ws?.close();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomId, token]);

  // Real WebRTC: getUserMedia capture + RTCPeerConnection mesh, signaled over the room
  // WebSocket already opened above. See use-webrtc-mesh.ts for the full explanation —
  // including what's genuinely still required (TURN server, live multi-browser testing)
  // that this hook can't provide on its own.
  const sendSignalling = useCallback((envelope: { type: string; data: Record<string, unknown> }) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(envelope));
    }
  }, []);
  const webrtc = useWebRTCMesh({ myConnectionId, sendSignalling, isMuted, isVideoOn });

  // The actual missing link: real mic audio -> meeting-server -> ai-server -> transcript.
  // Everything downstream of a transcript entry already worked (the `transcript` and
  // `translation` WS cases above, and meeting-server's now-wired auto-translate — see
  // apps/meeting-server/app/api/routes/meetings.py's _auto_translate_entry); what never
  // existed was anything producing a transcript entry from this room's actual audio.
  // Reuses the exact same resample-to-16kHz-PCM16 pipeline as the OTHER live-meeting
  // feature (src/lib/mic-capture.ts) — same audio format meeting-server's new audio_chunk
  // handler expects (see audio_transcription.py's docstring on why).
  useEffect(() => {
    if (!webrtc.localStream || isMuted || !wsConnected) return;
    const audioTrack = webrtc.localStream.getAudioTracks()[0];
    if (!audioTrack) return;

    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(new MediaStream([audioTrack]));
    // ScriptProcessorNode is deprecated in favor of AudioWorklet, but kept here on purpose —
    // identical reasoning and identical choice as the other live-meeting feature's capture
    // code (src/components/live-meeting.tsx): broad browser support without an extra
    // worklet-module file, and the processing here (resample + send) is light enough that
    // the main-thread cost ScriptProcessorNode is normally criticized for isn't significant
    // at this scale. Revisit both call sites together if that ever changes, not just one.
    const processor = audioContext.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (event) => {
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;
      const inputData = event.inputBuffer.getChannelData(0);
      const pcm16 = resampleAndEncode(inputData, audioContext.sampleRate, 16000);
      // base64-encode for a plain JSON WS message — meeting-server's room WebSocket loop
      // uses `receive_json()` exclusively (not a mixed text/binary `receive()`), so binary
      // frames aren't an option here without a larger protocol change; base64 inside JSON
      // is the correct fit for this connection as it exists today, not a workaround.
      let binary = "";
      const bytes = new Uint8Array(pcm16.buffer);
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      const pcm_b64 = btoa(binary);
      wsRef.current.send(JSON.stringify({ type: "audio_chunk", pcm: pcm_b64 }));
    };

    source.connect(processor);
    // Connecting to .destination is required for ScriptProcessorNode's onaudioprocess to
    // fire in every browser (a long-standing Web Audio API quirk, not a bug here) — the
    // gain stays effectively silent since this only feeds the processor, not the speakers.
    const silentGain = audioContext.createGain();
    silentGain.gain.value = 0;
    processor.connect(silentGain);
    silentGain.connect(audioContext.destination);

    return () => {
      processor.disconnect();
      source.disconnect();
      silentGain.disconnect();
      audioContext.close();
    };
  }, [webrtc.localStream, isMuted, wsConnected]);

  function handleWSMessage(data: Record<string, unknown>) {
    const type = data.type as string;
    switch (type) {
      case "room_state":
        if (data.connection_id) setMyConnectionId(data.connection_id as string);
        if (data.participants) {
          const mapped = (data.participants as Record<string, unknown>[]).map(mapParticipant);
          setParticipants(mapped);
          // Connect to everyone already in the room when we arrive — not just to people who
          // join after us (that's the participant_joined case below).
          mapped.forEach((p) => { if (p.connectionId) webrtc.connectToPeer(p.connectionId); });
        }
        if (data.transcript) setTranscript((data.transcript as Record<string, unknown>[]).map(mapTranscript));
        if (data.ai_state) setAiState(data.ai_state as unknown as AIState);
        if (data.whiteboard_strokes) setWhiteboardStrokes(data.whiteboard_strokes as Record<string, unknown>[]);
        break;
      case "offer":
      case "answer":
      case "ice_candidate":
        // These arrive as their own top-level message types, not wrapped — meeting-server's
        // route_message() forwards `data.get("data", {})` directly via ws.send_json(), with
        // no outer envelope (confirmed by reading apps/meeting-server/app/api/routes/
        // meetings.py directly, not assumed from how we send them — see sendSignalling
        // below, which DOES wrap outgoing messages in {type:"signalling", data:{...}} since
        // that outer shape is what the receive loop's `msg_type == "signalling"` branch
        // requires on the way IN; the server only forwards the inner part on the way OUT).
        webrtc.handleSignallingMessage(data as unknown as Parameters<typeof webrtc.handleSignallingMessage>[0]);
        break;
      case "transcript":
        if (data.entry) setTranscript(prev => [...prev, mapTranscript(data.entry as Record<string, unknown>)]);
        break;
      case "chat_message":
        if (data.message) setChatMessages(prev => [...prev, mapChatMsg(data.message as Record<string, unknown>)]);
        break;
      case "ai_update":
        if (data.ai_state) setAiState(prev => prev ? { ...prev, ...(data.ai_state as Record<string, unknown>) } as unknown as AIState : data.ai_state as unknown as AIState);
        break;
      case "participant_joined":
        if (data.participant) {
          const newP = mapParticipant(data.participant as Record<string, unknown>);
          setParticipants(prev => [...prev, newP]);
          if (newP.connectionId) webrtc.connectToPeer(newP.connectionId);
        }
        break;
      case "participant_left":
        setParticipants(prev => prev.filter(p => p.id !== (data.participant_id as string)));
        if (data.connection_id) webrtc.disconnectFromPeer(data.connection_id as string);
        break;
      case "media_state_changed":
        setParticipants(prev => prev.map(p => p.id === (data.participant_id as string) ? { ...p, isMuted: (data.media as Record<string, unknown>)?.audio_enabled === false, isVideoOn: (data.media as Record<string, unknown>)?.video_enabled !== false } : p));
        break;
      case "hand_raised":
        setParticipants(prev => prev.map(p => p.id === (data.participant_id as string) ? { ...p, handRaised: data.raised as boolean } : p));
        break;
      case "emoji_reaction": {
        // Previously had no receive handler at all — emoji reactions only ever existed on
        // the backend. Auto-removes itself after the float-up animation finishes (2.5s) so
        // this array doesn't grow unbounded over a long meeting.
        const id = `${Date.now()}-${Math.random()}`;
        setFloatingReactions(prev => [...prev, { id, emoji: (data.emoji as string) || "👍", leftPercent: 20 + Math.random() * 60 }]);
        setTimeout(() => setFloatingReactions(prev => prev.filter(r => r.id !== id)), 2600);
        break;
      }
      case "waiting_list_changed":
        // Real-time sync for the host's waiting-room panel — see HostWaitingPanel below,
        // which re-fetches the waiting list whenever this counter changes rather than
        // polling on a fixed interval the way the waiting participant's own admission-check
        // does. A push-triggered refetch here is correctly event-driven since a host is
        // already connected to this WS the whole time their panel is open.
        setWaitingListVersion(v => v + 1);
        break;
      case "whiteboard_stroke":
        if (data.stroke) setWhiteboardStrokes(prev => [...prev, data.stroke as Record<string, unknown>]);
        break;
      case "whiteboard_undo":
        setWhiteboardStrokes(prev => prev.filter(s => s.id !== data.stroke_id));
        break;
      case "whiteboard_clear":
        setWhiteboardStrokes([]);
        break;
    }
  }

  function mapParticipant(p: Record<string, unknown>): Participant {
    const media = (p.media || {}) as Record<string, unknown>;
    return {
      id: p.id as string,
      user_id: (p.user_id as string) || "",
      name: (p.display_name as string) || "Participant",
      isHost: p.role === "host",
      isMuted: media.audio_enabled === false,
      isVideoOn: media.video_enabled !== false,
      isScreenSharing: media.screen_sharing === true,
      isSpeaking: p.is_speaking === true,
      handRaised: p.hand_raised === true,
      connectionQuality: (p.connection_quality as "good" | "fair" | "poor") || "good",
      connectionId: p.connection_id as string | undefined,
    };
  }

  function mapTranscript(e: Record<string, unknown>): TranscriptEntry {
    return {
      id: e.id as string,
      speaker_id: (e.speaker_id as string) || "",
      speaker_name: (e.speaker_name as string) || "Unknown",
      text: (e.text as string) || "",
      timestamp_ms: (e.timestamp_ms as number) || 0,
      kind: (e.kind as string) || "statement",
      created_at: (e.created_at as string) || "",
    };
  }

  function mapChatMsg(m: Record<string, unknown>): ChatMsg {
    return {
      id: m.id as string,
      sender_id: (m.sender_id as string) || "",
      sender_name: (m.sender_name as string) || "Unknown",
      content: (m.content as string) || "",
      created_at: (m.created_at as string) || "",
    };
  }

  const handleStart = (newRoomId: string, title: string, state?: string) => {
    setRoomId(newRoomId);
    setRoomTitle(title);
    setShowModal(false);
    if (!initialRoomId) router.replace(`/meeting/${newRoomId}`);
    if (state === "in_waiting_room") {
      setIsWaiting(true);
      return;
    }
    setInMeeting(true);
    // The actual URL fix: previously the address bar stayed on /rooms regardless of which
    // room you created/joined, so there was nothing to share, bookmark, or survive a
    // refresh. router.replace (not push) so "back" from inside a meeting goes to wherever
    // you were before opening the picker, not to a stale empty modal state.
  };

  const handleLeave = async () => {
    if (roomId && token) {
      try { await api.leaveMeetingRoom(token, roomId); } catch { /* ignore */ }
    }
    wsRef.current?.close();
    if (initialRoomId) {
      // /meeting/{id} is this specific meeting's URL — leaving it should navigate away,
      // not flip back to a picker modal still sitting at the now-stale /meeting/{id} URL.
      router.push("/rooms");
      return;
    }
    setInMeeting(false);
    setShowModal(true);
    setRoomId("");
    setParticipants([]);
    setTranscript([]);
    setChatMessages([]);
    setAiState(null);
  };

  const handleSendChat = (content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "chat", content }));
    }
  };

  const handleRefreshAI = async () => {
    if (!roomId || !token) return;
    try {
      const res = await api.getMeetingAIState(token, roomId);
      if (res.ai_state) setAiState(res.ai_state as unknown as AIState);
    } catch { /* ignore */ }
  };

  if (!inMeeting) {
    if (isWaiting) {
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-ink px-4 text-center text-white">
          <div className="grid h-16 w-16 place-items-center rounded-full bg-white/10">
            <Clock className="h-7 w-7 animate-pulse text-white/70" />
          </div>
          <p className="text-lg font-medium">Waiting for the host to let you in…</p>
          <p className="max-w-sm text-sm text-white/55">
            You&rsquo;ll join automatically the moment the host admits you. No need to refresh.
          </p>
          <Button variant="secondary" onClick={() => { setIsWaiting(false); router.push("/rooms"); }}>
            Cancel
          </Button>
        </div>
      );
    }
    if (initialRoomId) {
      // Arrived via /meeting/{id} — never show the create/join modal here, that's the
      // whole point of having a dedicated route. Show a real loading/error state instead
      // of the blank `null` this branch used to fall through to for this case.
      if (autoJoinError) {
        return (
          <div className="flex h-screen flex-col items-center justify-center gap-4 bg-ink text-center text-white">
            <p className="text-lg font-medium">Couldn&rsquo;t join this meeting</p>
            <p className="max-w-sm text-sm text-white/55">{autoJoinError}</p>
            <Button variant="secondary" onClick={() => router.push("/rooms")}>Back to meetings</Button>
          </div>
        );
      }
      return (
        <div className="flex h-screen items-center justify-center bg-ink text-white/60">
          <p className="text-sm">Joining meeting…</p>
        </div>
      );
    }
    return showModal ? <CreateMeetingModal token={token} onClose={() => setShowModal(false)} onStart={handleStart} /> : null;
  }

  return (
    <div className="flex h-screen flex-col bg-ink">
      {webrtc.mediaError && (
        <div className="flex items-center justify-between gap-3 bg-[var(--danger)]/15 px-4 py-2 text-sm text-[var(--danger)]">
          <span>{webrtc.mediaError}</span>
        </div>
      )}
      {webrtc.recordingError && (
        <div className="flex items-center justify-between gap-3 bg-[var(--danger)]/15 px-4 py-2 text-sm text-[var(--danger)]">
          <span>{webrtc.recordingError}</span>
        </div>
      )}
      {webrtc.recordingBlobUrl && (
        <div className="flex items-center justify-between gap-3 bg-jade/10 px-4 py-2 text-sm text-jade">
          <span>Your recording is ready.</span>
          <a
            href={webrtc.recordingBlobUrl}
            download={`meeting-recording-${roomId}.${webrtc.recordingFileExtension}`}
            className="rounded-md bg-jade px-3 py-1 text-xs font-medium text-white hover:brightness-110"
          >
            Download
          </a>
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <div className="relative flex-1 flex flex-col">
          <FloatingReactions reactions={floatingReactions} />
          <div className="flex-1 p-3 sm:p-4 overflow-auto">
            {participants.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="mx-auto mb-4 h-16 w-16 rounded-full bg-brand/20 flex items-center justify-center">
                    <Users className="h-8 w-8 text-brand" />
                  </div>
                  <p className="text-white/70 text-lg font-medium">Waiting for participants...</p>
                  <p className="text-white/40 text-sm mt-2">Share the meeting link to invite others</p>
                  <p className="text-white/30 text-xs mt-4 font-mono">{roomId}</p>
                </div>
              </div>
            ) : (() => {
              // Shared resolver — was duplicated three times across gallery/speaker/(now
              // pin-driven spotlight) branches; pulled out once here rather than copying a
              // fourth time for the new pinned-spotlight case below.
              const resolve = (p: Participant) => {
                const isLocal = !!p.connectionId && p.connectionId === myConnectionId;
                const stream = isLocal ? webrtc.localStream : (p.connectionId ? webrtc.remotePeers[p.connectionId]?.stream : null);
                return { isLocal, stream };
              };
              const pinned = pinnedParticipantId ? participants.find(p => p.id === pinnedParticipantId) : null;

              // A pin overrides the gallery/speaker toggle entirely — true spotlight mode,
              // same behavior Google Meet's pin has: whoever's pinned takes the main stage
              // regardless of which layout you were just in, until unpinned.
              if (pinned) {
                const { isLocal, stream } = resolve(pinned);
                return (
                  <div className="h-full flex flex-col gap-3">
                    <div className="flex-1">
                      <ParticipantTile participant={pinned} large stream={stream} isLocal={isLocal} isPinned onTogglePin={() => setPinnedParticipantId(null)} />
                    </div>
                    <div className="flex gap-2 overflow-x-auto pb-1">
                      {participants.filter(p => p.id !== pinned.id).map((p) => {
                        const r = resolve(p);
                        return (
                          <div key={p.id} className="w-32 sm:w-40 shrink-0">
                            <ParticipantTile participant={p} stream={r.stream} isLocal={r.isLocal} onTogglePin={() => setPinnedParticipantId(p.id)} />
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              }

              if (viewMode === "gallery") {
                return (
                  <div className="grid h-full gap-2 sm:gap-3 auto-rows-fr" style={{ gridTemplateColumns: `repeat(${Math.min(participants.length, participants.length <= 2 ? 2 : participants.length <= 4 ? 2 : 3)}, 1fr)` }}>
                    {participants.map((p) => {
                      const { isLocal, stream } = resolve(p);
                      return <ParticipantTile key={p.id} participant={p} large={participants.length <= 2} stream={stream} isLocal={isLocal} onTogglePin={() => setPinnedParticipantId(p.id)} />;
                    })}
                  </div>
                );
              }

              return (
                <div className="h-full flex flex-col gap-3">
                  {participants[0] && (() => {
                    const { isLocal, stream } = resolve(participants[0]);
                    return <ParticipantTile participant={participants[0]} large stream={stream} isLocal={isLocal} onTogglePin={() => setPinnedParticipantId(participants[0].id)} />;
                  })()}
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {participants.slice(1).map((p) => {
                      const { isLocal, stream } = resolve(p);
                      return (
                        <div key={p.id} className="w-32 sm:w-40 shrink-0">
                          <ParticipantTile participant={p} stream={stream} isLocal={isLocal} onTogglePin={() => setPinnedParticipantId(p.id)} />
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })()}
          </div>
          <div className="flex sm:hidden items-center justify-center gap-2 pb-2 px-4">
            <button onClick={() => setSidePanel(sidePanel === "chat" ? "none" : "chat")} className={cn("flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs", sidePanel === "chat" ? "bg-brand text-white" : "bg-white/10 text-white/70")}>
              <MessageSquare className="h-3.5 w-3.5" /> Chat
            </button>
            <button onClick={() => setSidePanel(sidePanel === "ai" ? "none" : "ai")} className={cn("flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs", sidePanel === "ai" ? "bg-brand text-white" : "bg-white/10 text-white/70")}>
              <Bot className="h-3.5 w-3.5" /> AI
            </button>
            <button onClick={() => setSidePanel(sidePanel === "participants" ? "none" : "participants")} className={cn("flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs", sidePanel === "participants" ? "bg-brand text-white" : "bg-white/10 text-white/70")}>
              <Users className="h-3.5 w-3.5" /> {participants.length}
            </button>
          </div>
        </div>
        <div className={cn("hidden sm:block transition-all duration-300 overflow-hidden", sidePanel === "none" ? "w-0" : "w-80 xl:w-96")}>
          {sidePanel === "chat" && <ChatPanel messages={chatMessages} roomId={roomId} token={token} onSend={handleSendChat} />}
          {sidePanel === "participants" && <ParticipantsPanel participants={participants} />}
          {sidePanel === "ai" && <AIPanel aiState={aiState} transcript={transcript} roomId={roomId} token={token} onRefresh={handleRefreshAI} />}
          {sidePanel === "waiting" && amIHost && <HostWaitingPanel token={token} roomId={roomId} refreshSignal={waitingListVersion} />}
          {sidePanel === "whiteboard" && (
            <div className="w-[420px] border-l border-surface">
              <Whiteboard
                initialStrokes={whiteboardStrokes as unknown as React.ComponentProps<typeof Whiteboard>["initialStrokes"]}
                onDraw={(stroke) => sendWhiteboardDraw(stroke)}
                onUndo={sendWhiteboardUndo}
                onRedo={sendWhiteboardRedo}
                onClear={sendWhiteboardClear}
              />
            </div>
          )}
        </div>
        {sidePanel !== "none" && (
          <div className="fixed inset-0 z-40 sm:hidden" onClick={() => setSidePanel("none")}>
            <div className="absolute inset-0 bg-black/50" />
            <div className="absolute inset-y-0 right-0 w-80 animate-slide-in-right" onClick={(e) => e.stopPropagation()}>
              {sidePanel === "chat" && <ChatPanel messages={chatMessages} roomId={roomId} token={token} onSend={handleSendChat} />}
              {sidePanel === "participants" && <ParticipantsPanel participants={participants} />}
              {sidePanel === "ai" && <AIPanel aiState={aiState} transcript={transcript} roomId={roomId} token={token} onRefresh={handleRefreshAI} />}
          {sidePanel === "waiting" && amIHost && <HostWaitingPanel token={token} roomId={roomId} refreshSignal={waitingListVersion} />}
          {sidePanel === "whiteboard" && (
            <div className="w-[420px] border-l border-surface">
              <Whiteboard
                initialStrokes={whiteboardStrokes as unknown as React.ComponentProps<typeof Whiteboard>["initialStrokes"]}
                onDraw={(stroke) => sendWhiteboardDraw(stroke)}
                onUndo={sendWhiteboardUndo}
                onRedo={sendWhiteboardRedo}
                onClear={sendWhiteboardClear}
              />
            </div>
          )}
            </div>
          </div>
        )}
      </div>
      <MeetingToolbar
        isMuted={isMuted} setIsMuted={setIsMuted}
        isVideoOn={isVideoOn} setIsVideoOn={setIsVideoOn}
        isScreenSharing={webrtc.isScreenSharing} setIsScreenSharing={webrtc.toggleScreenShare}
        isRecording={webrtc.isRecording} isRecordingPaused={webrtc.isRecordingPaused} recordingSeconds={webrtc.recordingSeconds}
        onStartRecording={webrtc.startRecording} onStopRecording={webrtc.stopRecording}
        onPauseRecording={webrtc.pauseRecording} onResumeRecording={webrtc.resumeRecording}
        handRaised={handRaised} setHandRaised={setHandRaised}
        onSendEmoji={sendEmoji}
        sidePanel={sidePanel} setSidePanel={setSidePanel}
        viewMode={viewMode} setViewMode={setViewMode}
        elapsed={elapsed}
        onLeave={handleLeave}
        isHost={amIHost} token={token} roomId={roomId} isLocked={isLocked}
        onLockChange={setIsLocked} onEndMeeting={handleLeave}
      />
    </div>
  );
}
