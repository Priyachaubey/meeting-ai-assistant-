"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Video, Users, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

// The actual /meeting home page this document asked for — "Meeting experience starts from
// /meeting not modal windows." Previously /meeting/[meetingId] existed (built last pass) but
// /meeting itself (no ID) 404'd, and the only entry point was /rooms's CreateMeetingModal —
// a literal popup overlay. This page is the real fix: create/join happen inline on the page
// itself, not in a dialog, then navigate to the real per-meeting URL.

export default function MeetingHomePage() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token) || "";
  const [tab, setTab] = useState<"create" | "join">("create");
  const [title, setTitle] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleCreate() {
    setLoading(true);
    setError("");
    try {
      const room = await api.createMeetingRoom(token, { title: title || "New Meeting" });
      router.push(`/meeting/${room.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create meeting");
      setLoading(false);
    }
  }

  function handleJoin() {
    if (!joinCode.trim()) return;
    // The join page itself (MeetingRoom's auto-join effect, via initialRoomId) does the real
    // api.joinMeetingRoom() call and surfaces a real error if the code is bad — no need to
    // duplicate that request here, just get the ID out of a pasted code or full link.
    const roomId = joinCode.includes("/") ? joinCode.trim().split("/").filter(Boolean).pop()! : joinCode.trim();
    router.push(`/meeting/${roomId}`);
  }

  return (
    <div className="mx-auto flex min-h-[80vh] max-w-2xl flex-col justify-center px-4 py-12">
      <div className="text-center">
        <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-brand-gradient text-white">
          <Video className="h-7 w-7" />
        </div>
        <h1 className="text-3xl font-semibold">Start or join a meeting</h1>
        <p className="mt-2 text-ink-secondary">Real-time transcript, translation, and AI notes — automatically.</p>
      </div>

      <div className="mt-8 rounded-2xl border border-surface bg-elevated shadow-soft">
        <div className="flex border-b border-surface">
          <button
            onClick={() => setTab("create")}
            className={cn(
              "flex-1 py-3.5 text-sm font-medium transition-colors border-b-2",
              tab === "create" ? "text-brand border-brand" : "text-ink-tertiary border-transparent hover:text-ink-secondary"
            )}
          >
            New meeting
          </button>
          <button
            onClick={() => setTab("join")}
            className={cn(
              "flex-1 py-3.5 text-sm font-medium transition-colors border-b-2",
              tab === "join" ? "text-brand border-brand" : "text-ink-tertiary border-transparent hover:text-ink-secondary"
            )}
          >
            Join with a code
          </button>
        </div>

        <div className="p-6">
          {error && <p className="mb-4 text-sm text-[var(--danger)]">{error}</p>}

          {tab === "create" ? (
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium">Meeting title</label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Weekly standup"
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                  className="w-full rounded-lg border border-surface bg-surface-hover px-3.5 py-2.5 text-sm outline-none focus:border-brand placeholder:text-ink-placeholder"
                />
              </div>
              <Button className="w-full" onClick={handleCreate} disabled={loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Video className="h-4 w-4" />}
                Start meeting
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium">Meeting code or link</label>
                <input
                  value={joinCode}
                  onChange={(e) => setJoinCode(e.target.value)}
                  placeholder="meeting-room-uuid or full link"
                  onKeyDown={(e) => e.key === "Enter" && handleJoin()}
                  className="w-full rounded-lg border border-surface bg-surface-hover px-3.5 py-2.5 text-sm outline-none focus:border-brand placeholder:text-ink-placeholder"
                />
              </div>
              <Button className="w-full" onClick={handleJoin} disabled={!joinCode.trim()}>
                <ArrowRight className="h-4 w-4" /> Join meeting
              </Button>
            </div>
          )}
        </div>
      </div>

      <button
        onClick={() => router.push("/rooms")}
        className="mx-auto mt-6 flex items-center gap-1.5 text-sm text-ink-tertiary hover:text-ink-secondary"
      >
        <Users className="h-3.5 w-3.5" /> Looking for the full meeting list? Go to Rooms
      </button>
    </div>
  );
}
