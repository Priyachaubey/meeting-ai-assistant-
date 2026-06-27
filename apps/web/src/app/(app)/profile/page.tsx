"use client";
import { useEffect, useState } from "react";
import { UserCircle } from "lucide-react";
import { Button } from "@/components/button";
import { api, ApiError, NetworkError, type UserOut } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

export default function ProfilePage() {
  const token = useAuthStore((s) => s.token);
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fullName, setFullName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!token) return;
    api
      .getProfile(token)
      .then((u) => {
        setUser(u);
        setFullName(u.full_name ?? "");
      })
      .catch((err) => setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not load profile."))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSaving(true);
    setSaved(false);
    try {
      const updated = await api.updateProfile(token, { full_name: fullName });
      setUser(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not save profile.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <section className="p-6 text-ink/55">Loading profile…</section>;
  if (error || !user) return <section className="p-6 text-coral">{error ?? "Could not load profile."}</section>;

  return (
    <section className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Profile</h1>
      <div className="max-w-lg rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
        <div className="mb-5 flex items-center gap-3">
          <UserCircle className="h-10 w-10 text-iris" />
          <div>
            <p className="font-medium">{user.full_name || user.email}</p>
            <p className="text-sm text-ink/55">{user.email}</p>
          </div>
        </div>
        <form onSubmit={handleSave} className="space-y-3">
          <div>
            <label className="text-xs font-medium text-ink/60">Full name</label>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Your name"
              className="mt-1 w-full rounded-md border border-ink/15 px-3 py-2 text-sm"
            />
          </div>
          <div className="text-xs text-ink/45">
            Role: <span className="font-medium text-ink/65">{user.role}</span> · Member since{" "}
            {new Date(user.created_at).toLocaleDateString()}
          </div>
          <Button type="submit" disabled={saving} className="h-9 px-4 text-sm">
            {saving ? "Saving…" : "Save changes"}
          </Button>
          {saved && <span className="ml-3 text-sm text-jade">Saved.</span>}
        </form>
      </div>
    </section>
  );
}
