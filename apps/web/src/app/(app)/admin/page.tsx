"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, Database, Server, Users } from "lucide-react";
import { Button } from "@/components/button";
import {
  api,
  ApiError,
  NetworkError,
  type DetailedHealth,
  type MembershipOut,
  type SubscriptionOut,
  type UsageSummary,
  type WorkspaceOut,
} from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

function StatusDot({ ok }: { ok: boolean }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-jade" : "bg-coral"}`} />;
}

export default function AdminPage() {
  const token = useAuthStore((s) => s.token);
  const [workspace, setWorkspace] = useState<WorkspaceOut | null>(null);
  const [members, setMembers] = useState<MembershipOut[]>([]);
  const [subscription, setSubscription] = useState<SubscriptionOut | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [health, setHealth] = useState<DetailedHealth | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.listWorkspaces(token).then((ws) => {
      if (ws.length > 0) {
        setWorkspace(ws[0]);
        setName(ws[0].name);
        api.listMembers(token, ws[0].id).then(setMembers).catch(() => {});
      }
    });
    api.getSubscription(token).then(setSubscription).catch(() => {});
    api.getUsageSummary(token, 30).then(setUsage).catch(() => {});
    api.getDetailedHealth(token).then(setHealth).catch((err) => setHealthError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Unavailable"));
  }, [token]);

  async function handleRename(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !workspace || !name.trim()) return;
    setSaving(true);
    setSaved(false);
    try {
      const updated = await api.renameWorkspace(token, workspace.id, name.trim());
      setWorkspace(updated);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  const owners = members.filter((m) => m.role === "owner").length;
  const admins = members.filter((m) => m.role === "admin").length;

  return (
    <section className="p-6">
      <h1 className="mb-1 text-2xl font-semibold">Admin</h1>
      <p className="mb-6 text-sm text-ink/55">
        Workspace settings, members, billing, AI usage, and system status for{" "}
        {workspace?.name ?? "your workspace"}.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
          <h2 className="mb-3 font-semibold">Workspace settings</h2>
          {workspace?.my_role !== "owner" ? (
            <p className="text-sm text-ink/50">Only the workspace owner can rename it.</p>
          ) : (
            <form onSubmit={handleRename} className="flex gap-2">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="flex-1 rounded-md border border-ink/15 px-3 py-2 text-sm"
              />
              <Button type="submit" disabled={saving} className="h-9 px-3 text-sm">
                {saving ? "Saving…" : "Save"}
              </Button>
            </form>
          )}
          {saved && <p className="mt-2 text-sm text-jade">Saved.</p>}
        </div>

        <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Members</h2>
            <Link href="/team" className="text-sm text-iris hover:underline">
              Manage →
            </Link>
          </div>
          <div className="flex items-center gap-2 text-sm text-ink/72">
            <Users className="h-4 w-4 text-iris" />
            {members.length} member{members.length === 1 ? "" : "s"} · {owners} owner{owners === 1 ? "" : "s"} ·{" "}
            {admins} admin{admins === 1 ? "" : "s"}
          </div>
        </div>

        <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Billing</h2>
            <Link href="/billing" className="text-sm text-iris hover:underline">
              Manage →
            </Link>
          </div>
          {subscription ? (
            <p className="text-sm text-ink/72">
              <span className="font-medium capitalize">{subscription.plan}</span> plan · {subscription.status}
            </p>
          ) : (
            <p className="text-sm text-ink/45">Loading…</p>
          )}
        </div>

        <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">AI usage (30d)</h2>
            <Link href="/analytics" className="text-sm text-iris hover:underline">
              Full report →
            </Link>
          </div>
          {usage ? (
            <p className="text-sm text-ink/72">
              {usage.total_events} calls · ${usage.total_cost_usd.toFixed(4)} ·{" "}
              {usage.success_rate !== null ? `${Math.round(usage.success_rate * 100)}% success` : "no data"}
            </p>
          ) : (
            <p className="text-sm text-ink/45">Loading…</p>
          )}
        </div>

        <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft lg:col-span-2">
          <div className="mb-3 flex items-center gap-2">
            <Activity className="h-4 w-4 text-iris" />
            <h2 className="font-semibold">System health</h2>
          </div>
          {healthError && <p className="text-sm text-coral">{healthError}</p>}
          {health && (
            <div className="grid gap-3 md:grid-cols-3">
              <div className="flex items-center gap-2 text-sm">
                <Database className="h-4 w-4 text-ink/40" />
                <StatusDot ok={health.database.ok} />
                Database{health.database.latency_ms ? ` — ${health.database.latency_ms}ms` : ""}
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Server className="h-4 w-4 text-ink/40" />
                <StatusDot ok={health.qdrant.ok} />
                Qdrant{health.qdrant.latency_ms ? ` — ${health.qdrant.latency_ms}ms` : ""}
              </div>
              <div className="text-sm text-ink/55">
                Providers:{" "}
                {Object.entries(health.providers_configured)
                  .filter(([, on]) => on)
                  .map(([name]) => name)
                  .join(", ") || "none configured"}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
