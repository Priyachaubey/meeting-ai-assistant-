"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/button";
import { api, ApiError, NetworkError } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

export default function LoginPage() {
  const router = useRouter();
  const setToken = useAuthStore((s) => s.setToken);

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = mode === "login" ? await api.login(email, password) : await api.register(email, password);
      setToken(response.access_token);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else if (err instanceof NetworkError) setError(err.message);
      else setError("Unexpected error — check the browser console for details.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[linear-gradient(180deg,#fbfcfd_0%,#eef2f5_45%,#f8fafb_100%)] p-4">
      <div className="w-full max-w-sm rounded-lg border border-ink/10 bg-white/82 p-7 shadow-glow backdrop-blur-2xl">
        <Image src="/brand/icon-mark.png" alt="" width={48} height={48} className="mb-3 h-12 w-12" />
        <p className="mb-1 inline-flex items-center gap-2 rounded-md border border-jade/30 bg-jade/10 px-3 py-1 text-xs font-medium">
          <Sparkles className="h-3.5 w-3.5" />
          Microtechnique AI Meeting
        </p>
        <h1 className="mt-4 text-2xl font-semibold">{mode === "login" ? "Welcome back" : "Create your workspace"}</h1>

        <form onSubmit={onSubmit} className="mt-6 space-y-3">
          <div>
            <label className="text-xs font-medium text-ink/60">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-md border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-ink/40"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-ink/60">Password</label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-ink/40"
            />
          </div>

          {error && <p className="rounded-md bg-coral/10 px-3 py-2 text-sm text-coral">{error}</p>}

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </Button>
        </form>

        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="mt-4 w-full text-center text-sm text-ink/55 hover:text-ink"
        >
          {mode === "login" ? "Need a workspace? Register" : "Already have an account? Log in"}
        </button>
      </div>
    </main>
  );
}
