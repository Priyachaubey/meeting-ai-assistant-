"use client";
import { useEffect, useRef, useState } from "react";
import { Download, FileText, Trash2, UploadCloud } from "lucide-react";
import { api, ApiError, NetworkError, type DocumentOut, type KnowledgeSearchResult } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function KnowledgePage() {
  const token = useAuthStore((s) => s.token);
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api.listDocuments(token).then(setDocuments).catch(() => {});
  }, [token]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    setUploadStatus(`Uploading ${file.name}…`);
    try {
      const doc = await api.uploadKnowledgeDocument(token, file);
      setUploadStatus(`Indexed and stored ${doc.filename} (${formatBytes(doc.size_bytes)}).`);
      setDocuments((prev) => [doc, ...prev]);
    } catch (err) {
      setUploadStatus(err instanceof ApiError ? `Upload failed: ${err.message}` : "Upload failed.");
    }
  }

  async function handleDownload(documentId: string) {
    if (!token) return;
    try {
      const { url } = await api.getDocumentDownloadUrl(token, documentId);
      window.open(url, "_blank");
    } catch (err) {
      setUploadStatus(err instanceof ApiError ? `Could not get download link: ${err.message}` : "Could not get download link.");
    }
  }

  async function handleDelete(documentId: string) {
    if (!token) return;
    try {
      await api.deleteDocument(token, documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
    } catch (err) {
      setUploadStatus(err instanceof ApiError ? `Could not delete: ${err.message}` : "Could not delete.");
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || !token) return;
    setSearching(true);
    setError(null);
    try {
      const { results } = await api.searchKnowledge(token, query.trim());
      setResults(results);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <section className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Knowledge Base</h1>
      <div className="grid gap-4 lg:grid-cols-[.8fr_1.2fr]">
        <div>
          <div
            onClick={() => fileInput.current?.click()}
            className="cursor-pointer rounded-lg border border-dashed border-ink/20 bg-white p-8 text-center"
          >
            <input ref={fileInput} type="file" className="hidden" onChange={handleUpload} accept=".pdf,.docx,.pptx,.xlsx,.xls,.txt,.csv,.md" />
            <UploadCloud className="mx-auto mb-4 h-8 w-8 text-iris" />
            <p className="font-medium">Upload PDF, DOCX, PPTX, Excel, TXT, CSV, or Markdown</p>
            <p className="mt-2 text-sm text-ink/55">Stored for real and indexed for retrieval — shared with your workspace.</p>
            {uploadStatus && <p className="mt-3 text-sm text-ink/72">{uploadStatus}</p>}
          </div>

          <div className="mt-4 rounded-lg border border-ink/10 bg-white">
            <div className="border-b border-ink/8 p-3 text-sm font-medium text-ink/55">
              {documents.length} document{documents.length === 1 ? "" : "s"}
            </div>
            {documents.length === 0 && <p className="p-4 text-sm text-ink/45">No documents uploaded yet.</p>}
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between border-b border-ink/8 p-3 last:border-b-0">
                <div className="flex items-center gap-2 overflow-hidden">
                  <FileText className="h-4 w-4 shrink-0 text-iris" />
                  <div className="overflow-hidden">
                    <p className="truncate text-sm">{doc.filename}</p>
                    <p className="text-xs text-ink/40">{formatBytes(doc.size_bytes)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => handleDownload(doc.id)} className="text-ink/40 hover:text-iris">
                    <Download className="h-4 w-4" />
                  </button>
                  <button onClick={() => handleDelete(doc.id)} className="text-ink/40 hover:text-coral">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-ink/10 bg-white p-5">
          <h2 className="font-semibold">Search</h2>
          <form onSubmit={handleSearch} className="mt-3 flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about your uploaded documents…"
              className="flex-1 rounded-md border border-ink/15 px-3 py-2 text-sm"
            />
            <button type="submit" disabled={searching} className="rounded-md bg-ink px-4 text-sm text-white">
              {searching ? "…" : "Search"}
            </button>
          </form>
          {error && <p className="mt-3 text-sm text-coral">{error}</p>}
          <div className="mt-4 space-y-2">
            {results.length === 0 && !searching && (
              <p className="rounded-md bg-mist p-4 text-sm text-ink/64">
                No results yet. Upload a document above, then search — retrieval runs through
                real OpenAI embeddings + Qdrant now (see AUDIT.md §11).
              </p>
            )}
            {results.map((r, i) => (
              <div key={`${r.document_id}-${i}`} className="rounded-md bg-mist p-3 text-sm">
                <p className="text-ink/72">{r.text}</p>
                <p className="mt-1 text-xs text-ink/40">score {r.score.toFixed(2)}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
