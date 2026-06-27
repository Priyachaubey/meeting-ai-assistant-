"use client";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Gauge,
  HelpCircle,
  Languages,
  Mail,
  MessageSquareText,
  Send,
  Share2,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/button";
import { api, ApiError, NetworkError, type MeetingDetail, type ShareLinkOut } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

function formatTimestamp(ms: number) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function scoreColor(score: number) {
  if (score >= 70) return "text-jade";
  if (score >= 40) return "text-ink";
  return "text-coral";
}

export default function MeetingDeepDivePage() {
  const params = useParams<{ id: string }>();
  const meetingId = params.id;
  const token = useAuthStore((s) => s.token);

  const [detail, setDetail] = useState<MeetingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTimestamp, setActiveTimestamp] = useState<number | null>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);

  const [askQuestion, setAskQuestion] = useState("");
  const [askAnswer, setAskAnswer] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);

  const [emailDraft, setEmailDraft] = useState<{ subject: string; body: string } | null>(null);
  const [followUpMessage, setFollowUpMessage] = useState<string | null>(null);
  const [generating, setGenerating] = useState<"email" | "followup" | null>(null);
  const [generatorError, setGeneratorError] = useState<string | null>(null);

  const [translateLang, setTranslateLang] = useState("hi");
  const [translatedSummary, setTranslatedSummary] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);
  const [translateError, setTranslateError] = useState<string | null>(null);

  const [shareLinks, setShareLinks] = useState<ShareLinkOut[]>([]);
  const [newLinkToken, setNewLinkToken] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const [shareError, setShareError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !meetingId) return;
    setLoading(true);
    api
      .getMeetingDetail(token, meetingId)
      .then(setDetail)
      .catch((err) => setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not load this meeting."))
      .finally(() => setLoading(false));
    api.listShareLinks(token, meetingId).then(setShareLinks).catch(() => {});
  }, [token, meetingId]);

  function jumpToTimestamp(ts: number) {
    setActiveTimestamp(ts);
    const el = transcriptRef.current?.querySelector(`[data-ts="${ts}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!askQuestion.trim() || !token) return;
    setAsking(true);
    setAskAnswer(null);
    try {
      const { answer } = await api.askKnowledgeAssistant(token, askQuestion.trim());
      setAskAnswer(answer);
    } catch (err) {
      setAskAnswer(
        err instanceof ApiError || err instanceof NetworkError ? `[Unavailable: ${err.message}]` : "[Unavailable]"
      );
    } finally {
      setAsking(false);
    }
  }

  async function handleGenerateEmail() {
    if (!token || !meetingId) return;
    setGenerating("email");
    setGeneratorError(null);
    try {
      setEmailDraft(await api.generateEmailDraft(token, meetingId));
    } catch (err) {
      setGeneratorError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not generate an email draft.");
    } finally {
      setGenerating(null);
    }
  }

  async function handleGenerateFollowUp() {
    if (!token || !meetingId) return;
    setGenerating("followup");
    setGeneratorError(null);
    try {
      const { message } = await api.generateFollowUp(token, meetingId);
      setFollowUpMessage(message);
    } catch (err) {
      setGeneratorError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not generate a follow-up message.");
    } finally {
      setGenerating(null);
    }
  }

  async function handleTranslateSummary() {
    if (!token || !detail?.summary) return;
    setTranslating(true);
    setTranslateError(null);
    try {
      const { translated_text } = await api.translateText(token, detail.summary, translateLang);
      setTranslatedSummary(translated_text);
    } catch (err) {
      setTranslateError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Translation failed.");
    } finally {
      setTranslating(false);
    }
  }

  async function handleCreateShareLink() {
    if (!token || !meetingId) return;
    setSharing(true);
    setShareError(null);
    try {
      const created = await api.createShareLink(token, meetingId);
      setNewLinkToken(created.token);
      setShareLinks((prev) => [created, ...prev]);
    } catch (err) {
      setShareError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not create share link.");
    } finally {
      setSharing(false);
    }
  }

  async function handleRevokeShareLink(linkId: string) {
    if (!token || !meetingId) return;
    try {
      await api.revokeShareLink(token, meetingId, linkId);
      setShareLinks((prev) => prev.map((l) => (l.id === linkId ? { ...l, revoked: true } : l)));
    } catch (err) {
      setShareError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not revoke link.");
    }
  }

  if (loading) return <section className="p-6 text-ink/55">Loading meeting…</section>;
  if (error || !detail) return <section className="p-6 text-coral">{error ?? "Meeting not found."}</section>;

  const cards: { title: string; icon: typeof CheckCircle2; items: string[]; empty: string }[] = [
    { title: "Action Items", icon: CheckCircle2, items: detail.action_items, empty: "None detected." },
    { title: "Key Decisions", icon: Sparkles, items: detail.decisions, empty: "None detected." },
    { title: "Risks", icon: AlertTriangle, items: detail.risks, empty: "None detected." },
    {
      title: "Questions",
      icon: HelpCircle,
      items: detail.questions.map((q) => `${q.speaker}: ${q.text}`),
      empty: "No questions detected.",
    },
    { title: "Follow-ups", icon: MessageSquareText, items: detail.follow_ups, empty: "None suggested yet." },
  ];

  return (
    <section className="p-4 sm:p-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink/45">Meeting Deep Dive</p>
          <h1 className="font-display text-2xl font-semibold">{detail.title}</h1>
          <p className="mt-1 text-sm text-ink/50">{new Date(detail.created_at).toLocaleString()}</p>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-ink/10 bg-white px-5 py-3 shadow-soft">
          <Gauge className={`h-7 w-7 ${scoreColor(detail.score.overall)}`} />
          <div>
            <p className={`text-2xl font-semibold ${scoreColor(detail.score.overall)}`}>{detail.score.overall}</p>
            <p className="text-xs text-ink/45">AI Score (heuristic)</p>
          </div>
        </div>
      </div>

      {!detail.summary && (
        <div className="mb-6 rounded-md border border-ink/10 bg-mist p-3 text-sm text-ink/60">
          No summary generated yet for this meeting.
        </div>
      )}
      {detail.summary && (
        <div className="mb-6 rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">Summary</h2>
            <div className="flex items-center gap-2">
              <select
                value={translateLang}
                onChange={(e) => setTranslateLang(e.target.value)}
                className="rounded-md border border-ink/15 px-2 py-1 text-xs"
              >
                <option value="hi">Hindi</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="ja">Japanese</option>
                <option value="zh">Chinese</option>
                <option value="ar">Arabic</option>
              </select>
              <button
                onClick={handleTranslateSummary}
                disabled={translating}
                className="flex items-center gap-1 rounded-md border border-ink/15 px-2 py-1 text-xs text-ink/65 hover:bg-mist"
              >
                <Languages className="h-3.5 w-3.5" />
                {translating ? "Translating…" : "Translate"}
              </button>
            </div>
          </div>
          <p className="text-ink/72">{detail.summary}</p>
          {translateError && <p className="mt-2 text-sm text-coral">{translateError}</p>}
          {translatedSummary && (
            <div className="mt-3 rounded-md border border-iris/20 bg-iris/5 p-3 text-sm text-ink/72">
              {translatedSummary}
            </div>
          )}
        </div>
      )}

      <div className="mb-6 grid gap-4 md:grid-cols-3 lg:grid-cols-5">
        {cards.map(({ title, icon: Icon, items, empty }) => (
          <div key={title} className="rounded-lg border border-ink/10 bg-white p-4 shadow-soft">
            <div className="mb-3 flex items-center gap-2">
              <Icon className="h-4 w-4 text-iris" />
              <h3 className="text-sm font-semibold">{title}</h3>
            </div>
            {items.length === 0 ? (
              <p className="text-xs text-ink/40">{empty}</p>
            ) : (
              <ul className="space-y-1.5 text-sm text-ink/72">
                {items.map((item, i) => (
                  <li key={i} className="leading-snug">
                    {item}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-soft">
          <h2 className="mb-3 font-semibold">Transcript</h2>
          {detail.transcript.length > 1 && (
            <div className="mb-4 flex gap-1 overflow-x-auto pb-2">
              {detail.transcript.map((line) => (
                <button
                  key={line.timestamp_ms}
                  onClick={() => jumpToTimestamp(line.timestamp_ms)}
                  title={`${formatTimestamp(line.timestamp_ms)} — ${line.text.slice(0, 40)}`}
                  className={`h-2 w-6 shrink-0 rounded-full transition ${
                    line.kind === "question" ? "bg-iris" : "bg-ink/15"
                  } ${activeTimestamp === line.timestamp_ms ? "ring-2 ring-iris ring-offset-1" : ""}`}
                />
              ))}
            </div>
          )}
          <div ref={transcriptRef} className="max-h-[480px] space-y-3 overflow-y-auto">
            {detail.transcript.length === 0 && <p className="text-sm text-ink/45">No transcript recorded.</p>}
            {detail.transcript.map((line) => (
              <div
                key={line.timestamp_ms}
                data-ts={line.timestamp_ms}
                onClick={() => setActiveTimestamp(line.timestamp_ms)}
                className={`cursor-pointer rounded-md border p-3 transition ${
                  activeTimestamp === line.timestamp_ms ? "border-iris/40 bg-iris/5" : "border-ink/8 bg-mist"
                }`}
              >
                <div className="mb-1 flex items-center justify-between text-xs text-ink/50">
                  <span>{line.speaker}</span>
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatTimestamp(line.timestamp_ms)}
                  </span>
                </div>
                <p className={line.kind === "question" ? "font-medium text-ink" : "text-ink/72"}>{line.text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-ink/10 bg-ink p-4 text-white shadow-glow">
            <div className="mb-3 flex items-center gap-2">
              <Bot className="h-5 w-5 text-jade" />
              <h2 className="font-semibold">Knowledge Assistant</h2>
            </div>
            <p className="mb-3 text-xs text-white/55">
              Ask about this meeting or anything in your knowledge base — searches uploaded
              documents and past meeting summaries together.
            </p>
            <form onSubmit={handleAsk} className="flex gap-2">
              <input
                value={askQuestion}
                onChange={(e) => setAskQuestion(e.target.value)}
                placeholder="What did we decide about pricing?"
                className="flex-1 rounded-md border border-white/15 bg-white/10 px-3 py-2 text-sm placeholder:text-white/40"
              />
              <button type="submit" disabled={asking} className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-white/15">
                <Send className="h-4 w-4" />
              </button>
            </form>
            {asking && <p className="mt-3 text-sm text-white/50">Thinking…</p>}
            {askAnswer && <p className="mt-3 rounded-md bg-white/10 p-3 text-sm">{askAnswer}</p>}
          </div>

          <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-soft">
            <h2 className="mb-3 font-semibold">AI Follow-up Center</h2>
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleGenerateEmail} disabled={generating === "email"} className="h-9 px-3 text-sm">
                <Mail className="h-4 w-4" />
                {generating === "email" ? "Generating…" : "Draft email"}
              </Button>
              <Button onClick={handleGenerateFollowUp} disabled={generating === "followup"} className="h-9 px-3 text-sm">
                <MessageSquareText className="h-4 w-4" />
                {generating === "followup" ? "Generating…" : "Draft follow-up"}
              </Button>
            </div>
            {generatorError && <p className="mt-3 text-sm text-coral">{generatorError}</p>}
            {emailDraft && (
              <div className="mt-3 rounded-md bg-mist p-3 text-sm">
                <p className="font-medium">{emailDraft.subject}</p>
                <p className="mt-1 whitespace-pre-wrap text-ink/72">{emailDraft.body}</p>
              </div>
            )}
            {followUpMessage && (
              <div className="mt-3 rounded-md bg-mist p-3 text-sm text-ink/72">{followUpMessage}</div>
            )}
          </div>

          <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-soft">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold">Share with a guest</h2>
              <Button onClick={handleCreateShareLink} disabled={sharing} className="h-9 px-3 text-sm">
                <Share2 className="h-4 w-4" />
                {sharing ? "Creating…" : "New link"}
              </Button>
            </div>
            <p className="mb-3 text-xs text-ink/45">
              Read-only access to this meeting's transcript and AI cards — no account needed,
              no access to anything else in your workspace. Expires in 7 days.
            </p>
            {shareError && <p className="mb-2 text-sm text-coral">{shareError}</p>}
            {newLinkToken && (
              <div className="mb-3 rounded-md border border-jade/30 bg-jade/5 p-3 text-xs">
                <p className="mb-1 font-medium text-ink">
                  Copy this now — it won&apos;t be shown again:
                </p>
                <code className="break-all text-ink/72">
                  {typeof window !== "undefined" ? window.location.origin : ""}/guest/{newLinkToken}
                </code>
              </div>
            )}
            {shareLinks.length === 0 ? (
              <p className="text-sm text-ink/45">No active links.</p>
            ) : (
              <div className="space-y-2">
                {shareLinks.map((link) => (
                  <div key={link.id} className="flex items-center justify-between rounded-md bg-mist p-2 text-xs">
                    <span className={link.revoked ? "text-ink/40 line-through" : "text-ink/65"}>
                      Expires {new Date(link.expires_at).toLocaleDateString()}
                    </span>
                    {!link.revoked && (
                      <button onClick={() => handleRevokeShareLink(link.id)} className="text-coral hover:underline">
                        Revoke
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-lg border border-ink/10 bg-white p-4 text-xs text-ink/45 shadow-soft">
            {detail.score.note}
          </div>
        </div>
      </div>
    </section>
  );
}
