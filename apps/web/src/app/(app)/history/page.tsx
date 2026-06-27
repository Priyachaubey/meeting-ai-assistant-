"use client";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { api, ApiError, NetworkError, type KnowledgeSearchResult } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

export default function HistoryPage() {
  const token = useAuthStore((s) => s.token);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<KnowledgeSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const { data: meetings, isLoading, error } = useQuery({
    queryKey: ["meetings", token],
    queryFn: () => api.listMeetings(token as string),
    enabled: !!token,
  });

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || !token) return;
    setSearching(true);
    setSearchError(null);
    try {
      const { results } = await api.searchKnowledge(token, query.trim());
      setResults(results);
    } catch (err) {
      setSearchError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <section className="p-6">
      <h1 className="mb-1 text-2xl font-semibold">Meeting Library</h1>
      <p className="mb-6 text-sm text-ink/55">Every recorded meeting, searchable in natural language.</p>

      <form onSubmit={handleSearch} className="mb-6 flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/35" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='Try "what did we decide about pricing last week?"'
            className="w-full rounded-md border border-ink/15 bg-white py-2.5 pl-10 pr-3 text-sm"
          />
        </div>
        <button type="submit" disabled={searching} className="rounded-md bg-ink px-4 text-sm text-white">
          {searching ? "…" : "Search"}
        </button>
      </form>

      {searchError && <p className="mb-4 text-sm text-coral">{searchError}</p>}

      {results && (
        <div className="mb-6 rounded-lg border border-ink/10 bg-white">
          <div className="border-b border-ink/8 p-3 text-sm font-medium text-ink/55">
            {results.length} result{results.length === 1 ? "" : "s"}
          </div>
          {results.length === 0 && <p className="p-4 text-sm text-ink/45">No matches yet.</p>}
          {results.map((r, i) => (
            <div key={`${r.document_id}-${i}`} className="border-b border-ink/8 p-4 last:border-b-0">
              <div className="mb-1 flex items-center gap-2 text-xs text-ink/45">
                <span className={`rounded px-1.5 py-0.5 ${r.source === "meeting" ? "bg-iris/10 text-iris" : "bg-ink/8"}`}>
                  {r.source === "meeting" ? "Meeting" : "Document"}
                </span>
                <span>{r.document_id}</span>
              </div>
              <p className="text-sm text-ink/72">{r.text}</p>
              {r.source === "meeting" && r.meeting_id && (
                <Link href={`/meetings/${r.meeting_id}`} className="mt-1 inline-block text-xs text-iris hover:underline">
                  Open meeting →
                </Link>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="rounded-lg border border-ink/10 bg-white">
        {error && <p className="p-4 text-sm text-coral">Could not load meetings — is the API running?</p>}
        {isLoading && <p className="p-4 text-sm text-ink/45">Loading…</p>}
        {!isLoading && meetings?.length === 0 && <p className="p-4 text-sm text-ink/45">No meetings yet.</p>}
        {meetings?.map((m) => (
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
