"use client";
import { useState, useCallback } from "react";
import { Search, FileText, MessageSquare, CheckCircle2, Brain, Globe, Clock, Sparkles } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

interface SearchResult {
  id: string;
  type: string;
  title: string;
  text: string;
  score: number;
  metadata: Record<string, unknown>;
}

const TYPE_ICONS: Record<string, typeof FileText> = {
  meeting: FileText,
  transcript: MessageSquare,
  document: FileText,
  action_item: CheckCircle2,
  decision: CheckCircle2,
  knowledge: Brain,
};

const TYPE_COLORS: Record<string, string> = {
  meeting: "text-brand bg-brand/10",
  transcript: "text-[#2563EB] bg-blue-100",
  document: "text-[#059669] bg-emerald-100",
  action_item: "text-[#D97706] bg-amber-100",
  decision: "text-[#7C3AED] bg-purple-100",
  knowledge: "text-[#0891B2] bg-cyan-100",
};

const FILTER_TYPES = [
  { id: "all", label: "All" },
  { id: "meeting", label: "Meetings" },
  { id: "transcript", label: "Transcripts" },
  { id: "document", label: "Documents" },
  { id: "action_item", label: "Action Items" },
  { id: "decision", label: "Decisions" },
  { id: "knowledge", label: "Knowledge" },
];

export default function SearchPage() {
  const token = useAuthStore((s) => s.token) || "";
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [activeFilter, setActiveFilter] = useState("all");
  const [total, setTotal] = useState(0);

  const handleSearch = useCallback(async () => {
    if (!query.trim() || !token) return;
    setLoading(true);
    setSearched(true);
    try {
      const docTypes = activeFilter === "all" ? undefined : [activeFilter];
      const res = await api.enterpriseSearch(token, query, docTypes);
      setResults(res.results || []);
      setTotal(res.total || 0);
    } catch {
      setResults([]);
      setTotal(0);
    }
    setLoading(false);
  }, [query, token, activeFilter]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  const filteredResults = activeFilter === "all"
    ? results
    : results.filter((r) => r.type === activeFilter);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Enterprise Search</h1>
        <p className="mt-2 text-sm text-ink-secondary">Search across meetings, transcripts, documents, action items, and knowledge base.</p>
      </div>

      {/* Search Bar */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-placeholder" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search meetings, transcripts, documents, action items..."
            className="w-full rounded-xl border border-surface bg-elevated pl-12 pr-28 py-3.5 text-base outline-none focus:border-brand transition-colors placeholder:text-ink-placeholder"
          />
          <Button
            onClick={handleSearch}
            loading={loading}
            className="absolute right-2 top-1/2 -translate-y-1/2"
          >
            Search
          </Button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="mb-6 flex flex-wrap gap-2">
        {FILTER_TYPES.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveFilter(id)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              activeFilter === id
                ? "gradient-brand text-white"
                : "bg-surface-hover text-ink-secondary hover:text-ink"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Results */}
      {searched && (
        <div>
          <p className="mb-4 text-sm text-ink-tertiary">
            {loading ? "Searching..." : `${filteredResults.length} results found`}
            {total > 0 && !loading && ` (${total} total)`}
          </p>

          {filteredResults.length === 0 && !loading && (
            <div className="rounded-xl border border-surface bg-elevated p-12 text-center">
              <Search className="mx-auto mb-3 h-10 w-10 text-ink-placeholder" />
              <p className="text-ink-secondary">No results found for &quot;{query}&quot;</p>
              <p className="mt-1 text-sm text-ink-tertiary">Try different keywords or adjust your filters.</p>
            </div>
          )}

          <div className="space-y-3">
            {filteredResults.map((result) => {
              const Icon = TYPE_ICONS[result.type] || FileText;
              const colorClass = TYPE_COLORS[result.type] || "text-ink-secondary bg-surface-hover";
              return (
                <div
                  key={result.id}
                  className="group rounded-xl border border-surface bg-elevated p-4 transition-all hover:border-brand/30 hover:shadow-sm"
                >
                  <div className="flex items-start gap-3">
                    <div className={cn("mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg", colorClass)}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-sm font-semibold truncate">{result.title}</h3>
                        <span className={cn("rounded-md px-2 py-0.5 text-xs font-medium capitalize", colorClass)}>
                          {result.type.replace("_", " ")}
                        </span>
                      </div>
                      <p className="text-sm text-ink-secondary line-clamp-2">{result.text}</p>
                      <div className="mt-2 flex items-center gap-3 text-xs text-ink-tertiary">
                        <span className="flex items-center gap-1">
                          <Sparkles className="h-3 w-3" />
                          {(result.score * 100).toFixed(0)}% match
                        </span>
                        {result.metadata?.created_at ? (
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {new Date(String(result.metadata.created_at)).toLocaleDateString()}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!searched && (
        <div className="rounded-xl border border-surface bg-elevated p-12 text-center">
          <Search className="mx-auto mb-3 h-10 w-10 text-ink-placeholder" />
          <p className="text-ink-secondary">Enter a search query to find meetings, documents, and more</p>
        </div>
      )}
    </div>
  );
}
