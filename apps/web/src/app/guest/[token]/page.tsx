"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";
import Image from "next/image";
import { api, ApiError, NetworkError, type GuestMeetingView } from "@/lib/api";

export default function GuestMeetingPage() {
  const params = useParams<{ token: string }>();
  const [detail, setDetail] = useState<GuestMeetingView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getGuestMeeting(params.token)
      .then(setDetail)
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? "This link is invalid, expired, or has been revoked."
            : err instanceof NetworkError
              ? err.message
              : "Could not load this meeting."
        )
      )
      .finally(() => setLoading(false));
  }, [params.token]);

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#fbfcfd_0%,#eef2f5_45%,#f8fafb_100%)] p-4 sm:p-8">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex items-center gap-3">
          <Image src="/brand/icon-mark.png" alt="" width={32} height={32} className="h-8 w-8" />
          <span className="font-medium">Microtechnique AI Meeting</span>
          <span className="rounded-md border border-ink/10 bg-white px-2 py-0.5 text-xs text-ink/45">Guest view</span>
        </div>

        {loading && <p className="text-ink/55">Loading…</p>}
        {error && (
          <div className="flex items-center gap-2 rounded-md border border-coral/20 bg-coral/10 p-4 text-sm text-coral">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {detail && (
          <div className="space-y-4">
            <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
              <h1 className="font-display text-2xl font-semibold">{detail.title}</h1>
              <p className="mt-1 text-sm text-ink/50">{new Date(detail.created_at).toLocaleString()}</p>
            </div>

            {detail.summary && (
              <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
                <h2 className="mb-2 flex items-center gap-2 font-semibold">
                  <Sparkles className="h-4 w-4 text-iris" /> Summary
                </h2>
                <p className="text-ink/72">{detail.summary}</p>
              </div>
            )}

            {detail.action_items.length > 0 && (
              <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
                <h2 className="mb-2 font-semibold">Action Items</h2>
                {detail.action_items.map((item, i) => (
                  <p key={i} className="mb-1 flex gap-2 text-sm text-ink/72">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-iris" />
                    {item}
                  </p>
                ))}
              </div>
            )}

            <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
              <h2 className="mb-3 font-semibold">Transcript</h2>
              <div className="max-h-[480px] space-y-3 overflow-y-auto">
                {detail.transcript.map((line, i) => (
                  <div key={i} className="rounded-md border border-ink/8 bg-mist p-3">
                    <p className="mb-1 text-xs text-ink/50">{line.speaker}</p>
                    <p className={line.kind === "question" ? "font-medium text-ink" : "text-ink/72"}>{line.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
