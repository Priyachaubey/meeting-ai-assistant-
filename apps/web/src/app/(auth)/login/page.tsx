"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { CheckCircle2, Eye, EyeOff, Sparkles, XCircle } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import { api, ApiError, NetworkError } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

/* ───────────────────────────── password strength ─────────────────────────────
   A real, deterministic scorer — not a fake animated bar. No new dependency:
   just length + character-class checks, which is genuinely what most strength
   meters are doing under the hood anyway. */

function passwordStrength(password: string): { score: 0 | 1 | 2 | 3 | 4; label: string } {
  if (!password) return { score: 0, label: "" };
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) score++;
  const clamped = Math.min(score, 4) as 0 | 1 | 2 | 3 | 4;
  const labels = ["Too short", "Weak", "Fair", "Good", "Strong"];
  return { score: clamped, label: labels[clamped] };
}

const STRENGTH_COLOR = ["bg-coral", "bg-coral", "bg-[#f7c948]", "bg-jade", "bg-jade"];

/* ───────────────────────────── left panel ───────────────────────────── */

const leftPanelStats = [
  ["<2s", "transcript latency"],
  ["200+", "languages translated live"],
  ["100%", "self-hostable AI engine"],
] as const;

function BrandPanel({ mode }: { mode: "login" | "register" }) {
  const reduce = useReducedMotion();
  return (
    <div className="relative hidden overflow-hidden bg-[linear-gradient(160deg,#1a0030_0%,#33005C_45%,#5B0A8C_100%)] p-10 text-white lg:flex lg:flex-col lg:justify-between">
      {!reduce && (
        <>
          <motion.div
            aria-hidden
            className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-[#8B1FC7]/30 blur-3xl"
            animate={{ x: [0, 30, 0], y: [0, 24, 0] }}
            transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            aria-hidden
            className="pointer-events-none absolute -right-16 bottom-10 h-72 w-72 rounded-full bg-jade/15 blur-3xl"
            animate={{ x: [0, -24, 0], y: [0, -18, 0] }}
            transition={{ duration: 13, repeat: Infinity, ease: "easeInOut" }}
          />
        </>
      )}

      <div className="relative">
        <Image src="/brand/icon-mark.png" alt="" width={40} height={40} className="h-10 w-10" />
        <motion.h2
          key={mode}
          initial={reduce ? undefined : { opacity: 0, y: 12 }}
          animate={reduce ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mt-10 max-w-sm text-3xl font-semibold leading-tight"
        >
          {mode === "login" ? "Your meetings, picked up right where AI left off." : "Set up a workspace your whole team can think alongside."}
        </motion.h2>
        <p className="mt-4 max-w-sm text-white/65">
          Live transcription, translation and meeting intelligence — running on a self-hosted
          AI engine you control.
        </p>
      </div>

      <div className="relative grid grid-cols-3 gap-3">
        {leftPanelStats.map(([value, label], index) => (
          <motion.div
            key={value}
            initial={reduce ? undefined : { opacity: 0, y: 10 }}
            animate={reduce ? undefined : { opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 + index * 0.08 }}
            className="rounded-lg border border-white/10 bg-white/[0.06] p-3"
          >
            <p className="text-lg font-semibold">{value}</p>
            <p className="mt-1 text-xs text-white/50">{label}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

/* ───────────────────────────── page ───────────────────────────── */

export default function LoginPage() {
  const router = useRouter();
  const setToken = useAuthStore((s) => s.setToken);
  const reduce = useReducedMotion();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [fullName, setFullName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Clear the confirm-password field's mismatch state whenever switching modes, so a half-
  // filled register form doesn't carry stale validation into a fresh login attempt.
  useEffect(() => {
    setError(null);
  }, [mode]);

  const strength = useMemo(() => passwordStrength(password), [password]);
  const passwordsMatch = mode === "login" || !confirmPassword || password === confirmPassword;
  const canSubmit =
    mode === "login"
      ? email.length > 0 && password.length > 0
      : email.length > 0 && password.length >= 8 && password === confirmPassword && agreedToTerms;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response =
        mode === "login"
          ? await api.login(email, password)
          : await api.register({
              email,
              password,
              full_name: fullName || undefined,
              workspace_name: workspaceName || undefined,
            });
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
    <main className="grid min-h-screen lg:grid-cols-2">
      <BrandPanel mode={mode} />

      <div className="grid place-items-center bg-mist p-4 sm:p-8">
        <motion.div
          initial={reduce ? undefined : { opacity: 0, y: 14 }}
          animate={reduce ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-sm rounded-lg border border-ink/10 bg-white p-7 shadow-glow"
        >
          <Image src="/brand/icon-mark.png" alt="" width={40} height={40} className="mb-3 h-10 w-10 lg:hidden" />
          <p className="mb-1 inline-flex items-center gap-2 rounded-md border border-jade/30 bg-jade/10 px-3 py-1 text-xs font-medium">
            <Sparkles className="h-3.5 w-3.5" /> Microtechnique AI Meeting
          </p>

          <AnimatePresence mode="wait">
            <motion.h1
              key={mode}
              initial={reduce ? undefined : { opacity: 0, x: 8 }}
              animate={reduce ? undefined : { opacity: 1, x: 0 }}
              exit={reduce ? undefined : { opacity: 0, x: -8 }}
              transition={{ duration: 0.2 }}
              className="mt-4 text-2xl font-semibold"
            >
              {mode === "login" ? "Welcome back" : "Create your workspace"}
            </motion.h1>
          </AnimatePresence>

          <form onSubmit={onSubmit} className="mt-6 space-y-3">
            {mode === "register" && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-ink/60">Full name</label>
                  <input
                    type="text"
                    autoComplete="name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="mt-1 w-full rounded-md border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-ink/40"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-ink/60">Company</label>
                  <input
                    type="text"
                    autoComplete="organization"
                    value={workspaceName}
                    onChange={(e) => setWorkspaceName(e.target.value)}
                    placeholder="Becomes your workspace name"
                    className="mt-1 w-full rounded-md border border-ink/15 bg-white px-3 py-2 text-sm outline-none placeholder:text-ink/30 focus:border-ink/40"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="text-xs font-medium text-ink/60">Email</label>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-md border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-ink/40"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-ink/60">Password</label>
              <div className="relative mt-1">
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-md border border-ink/15 bg-white px-3 py-2 pr-10 text-sm outline-none focus:border-ink/40"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink/40 hover:text-ink/70"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              {mode === "register" && password.length > 0 && (
                <div className="mt-2">
                  <div className="flex gap-1">
                    {[0, 1, 2, 3].map((i) => (
                      <motion.div
                        key={i}
                        className={cn("h-1 flex-1 rounded-full bg-ink/10", i < strength.score && STRENGTH_COLOR[strength.score])}
                        initial={false}
                        animate={{ opacity: i < strength.score ? 1 : 0.4 }}
                        transition={{ duration: 0.2 }}
                      />
                    ))}
                  </div>
                  <p className="mt-1 text-xs text-ink/45">{strength.label}</p>
                </div>
              )}
            </div>

            {mode === "register" && (
              <div>
                <label className="text-xs font-medium text-ink/60">Confirm password</label>
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className={cn(
                    "mt-1 w-full rounded-md border bg-white px-3 py-2 text-sm outline-none focus:border-ink/40",
                    passwordsMatch ? "border-ink/15" : "border-coral/50"
                  )}
                />
                <AnimatePresence>
                  {!passwordsMatch && (
                    <motion.p
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-1 flex items-center gap-1 text-xs text-coral"
                    >
                      <XCircle className="h-3 w-3" /> Passwords don&rsquo;t match
                    </motion.p>
                  )}
                  {passwordsMatch && confirmPassword.length > 0 && (
                    <motion.p
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-1 flex items-center gap-1 text-xs text-jade"
                    >
                      <CheckCircle2 className="h-3 w-3" /> Passwords match
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
            )}

            {mode === "register" && (
              <label className="flex items-start gap-2 text-xs text-ink/60">
                <input
                  type="checkbox"
                  checked={agreedToTerms}
                  onChange={(e) => setAgreedToTerms(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-ink/30"
                />
                I agree to the Terms of Service and Privacy Policy
              </label>
            )}

            {error && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="rounded-md bg-coral/10 px-3 py-2 text-sm text-coral"
              >
                {error}
              </motion.p>
            )}

            <Button type="submit" disabled={loading || !canSubmit} className="w-full">
              {loading ? "Please wait\u2026" : mode === "login" ? "Log in" : "Create account"}
            </Button>
          </form>

          <button
            type="button"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="mt-4 w-full text-center text-sm text-ink/55 hover:text-ink"
          >
            {mode === "login" ? "Need a workspace? Register" : "Already have an account? Log in"}
          </button>
        </motion.div>
      </div>
    </main>
  );
}
