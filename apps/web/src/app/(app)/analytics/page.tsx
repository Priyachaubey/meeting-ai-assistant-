"use client";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, AlertCircle, Clock, DollarSign } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

export default function AnalyticsPage() {
  const token = useAuthStore((s) => s.token);
  const { data, isLoading, error } = useQuery({
    queryKey: ["ai-usage", token],
    queryFn: () => api.getUsageSummary(token as string, 30),
    enabled: !!token,
  });

  const providerData = data
    ? Object.entries(data.by_provider).map(([provider, stats]) => ({ provider, cost: Number(stats.cost_usd.toFixed(4)) }))
    : [];

  const stats = data
    ? [
        [DollarSign, `$${data.total_cost_usd.toFixed(4)}`, "total AI cost (30d)"],
        [Activity, String(data.total_events), "AI calls"],
        [Clock, `${data.avg_latency_ms.toFixed(0)}ms`, "avg latency"],
        [AlertCircle, data.success_rate !== null ? `${Math.round(data.success_rate * 100)}%` : "—", "success rate"],
      ]
    : [];

  return (
    <section className="p-6">
      <h1 className="mb-1 text-2xl font-semibold">AI Performance Analytics</h1>
      <p className="mb-6 text-sm text-ink/55">
        Real token usage and cost, computed from every AI call made in the last 30 days.
      </p>

      {error && <p className="mb-4 text-sm text-coral">Could not load usage data — is the API running?</p>}
      {isLoading && <p className="text-sm text-ink/45">Loading…</p>}

      {data && (
        <>
          <div className="mb-6 grid gap-4 md:grid-cols-4">
            {stats.map(([Icon, value, label]) => (
              <div key={label as string} className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
                <Icon className="mb-3 h-5 w-5 text-iris" />
                <p className="text-2xl font-semibold">{value}</p>
                <p className="text-sm text-ink/55">{label}</p>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
            <h2 className="mb-4 font-semibold">Cost by provider</h2>
            {providerData.length === 0 ? (
              <p className="text-sm text-ink/45">
                No AI calls yet — start a live session or generate a meeting summary to see real
                usage here.
              </p>
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={providerData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(16,17,22,.08)" />
                    <XAxis dataKey="provider" />
                    <YAxis />
                    <Tooltip formatter={(value: number) => `$${value}`} />
                    <Bar dataKey="cost" fill="#5B0A8C" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
