"use client";
import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2, MessagesSquare, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

export default function DashboardPage() {
  const token = useAuthStore((s) => s.token);
  const { data: meetings, isLoading, error } = useQuery({
    queryKey: ["meetings", token],
    queryFn: () => api.listMeetings(token as string),
    enabled: !!token,
  });

  const total = meetings?.length ?? 0;
  const withSummary = meetings?.filter((m) => m.has_summary).length ?? 0;

  const stats = [
    [MessagesSquare, isLoading ? "…" : String(total), "meetings recorded"],
    [CheckCircle2, isLoading ? "…" : String(withSummary), "summaries generated"],
    [Activity, isLoading ? "…" : total > 0 ? `${Math.round((withSummary / total) * 100)}%` : "—", "completion rate"],
    [ShieldCheck, "Local-first", "capture control"],
  ] as const;

  return (
    <section className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Dashboard</h1>
      {error && <p className="mb-4 text-sm text-coral">Could not load meetings — is the API running?</p>}
      <div className="grid gap-4 md:grid-cols-4">
        {stats.map(([Icon, value, label]) => (
          <div key={label} className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
            <Icon className="mb-4 h-5 w-5 text-iris" />
            <p className="text-3xl font-semibold">{value}</p>
            <p className="text-sm text-ink/55">{label}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 rounded-lg border border-ink/10 bg-white">
        <div className="flex items-center justify-between border-b border-ink/8 p-4">
          <h2 className="font-semibold">Recent meetings</h2>
          <Link href="/history" className="text-sm text-ink/55 hover:text-ink">View all</Link>
        </div>
        {isLoading && <p className="p-4 text-sm text-ink/45">Loading…</p>}
        {!isLoading && total === 0 && <p className="p-4 text-sm text-ink/45">No meetings yet — start one from the Live tab.</p>}
        {meetings?.slice(0, 5).map((m) => (
          <Link
            key={m.id}
            href={`/meetings/${m.id}`}
            className="flex items-center justify-between border-b border-ink/8 p-4 last:border-b-0 hover:bg-mist"
          >
            <span>{m.title}</span>
            <span className="text-sm text-ink/50">{m.has_summary ? "Summary ready" : "No summary yet"}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
