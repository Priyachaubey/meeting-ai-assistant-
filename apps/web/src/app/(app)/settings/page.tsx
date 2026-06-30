"use client";
import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { api, ApiError, NetworkError } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

const MODES = [
  { value: "system", label: "System audio" },
  { value: "microphone", label: "Ambient microphone" },
  { value: "hybrid", label: "Hybrid mode" },
] as const;

// A small curated set, not all 200+ languages from the translation roadmap — this picker is
// for "what language do I want my own live view translated into," not an exhaustive language
// table. Real coverage depends on which languages the configured LLM provider actually
// translates well, which isn't something to claim without testing against a live provider.
const LANGUAGES = [
  { value: "en", label: "English (no translation)" },
  { value: "hi", label: "Hindi" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "ja", label: "Japanese" },
  { value: "zh", label: "Chinese" },
  { value: "ar", label: "Arabic" },
  { value: "pt", label: "Portuguese" },
  { value: "ru", label: "Russian" },
  { value: "gu", label: "Gujarati" },
  { value: "ta", label: "Tamil" },
] as const;

export default function SettingsPage() {
  const token = useAuthStore((s) => s.token);
  const [mode, setMode] = useState<string | null>(null);
  const [language, setLanguage] = useState<string>("en");
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .getProfile(token)
      .then((u) => {
        setMode(u.audio_capture_mode);
        setLanguage(u.preferred_language);
      })
      .catch(() => setError("Could not load settings."));
  }, [token]);

  async function selectMode(value: string) {
    if (!token || value === mode) return;
    setSaving(value);
    setError(null);
    try {
      const updated = await api.updateProfile(token, { audio_capture_mode: value });
      setMode(updated.audio_capture_mode);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not save setting.");
    } finally {
      setSaving(null);
    }
  }

  async function selectLanguage(value: string) {
    if (!token) return;
    setSaving(`lang:${value}`);
    setError(null);
    try {
      const updated = await api.updateProfile(token, { preferred_language: value });
      setLanguage(updated.preferred_language);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not save language.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <section className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Settings</h1>

      <div className="mb-4 rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
        <h2 className="font-semibold">Audio capture</h2>
        <p className="mt-1 text-sm text-ink/55">Saved to your profile — applies the next time you start a session.</p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {MODES.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => selectMode(value)}
              disabled={saving === value}
              className={`relative rounded-md border p-3 text-left transition ${
                mode === value ? "border-iris bg-iris/5" : "border-ink/10 hover:bg-mist"
              }`}
            >
              {label}
              {mode === value && <Check className="absolute right-3 top-3 h-4 w-4 text-iris" />}
              {saving === value && <span className="absolute right-3 top-3 text-xs text-ink/40">saving…</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
        <h2 className="font-semibold">Live translation language</h2>
        <p className="mt-1 text-sm text-ink/55">
          When you start a live session, your own transcript and AI suggestions are translated
          into this language automatically (set to English to disable).
        </p>
        <select
          value={language}
          onChange={(e) => selectLanguage(e.target.value)}
          className="mt-3 rounded-md border border-ink/15 px-3 py-2 text-sm"
        >
          {LANGUAGES.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
        {saving?.startsWith("lang:") && <span className="ml-2 text-xs text-ink/40">saving…</span>}
      </div>

      {error && <p className="mt-3 text-sm text-coral">{error}</p>}
    </section>
  );
}
