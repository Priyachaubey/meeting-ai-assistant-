"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  Mic,
  Globe,
  BrainCircuit,
  Search,
  ShieldCheck,
  CheckCircle2,
  Sparkles,
  Languages,
  AudioLines,
  Zap,
  ChevronDown,
  Server,
  Cpu,
  Users,
  MessageSquareText,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* ─── Design tokens (dark, from screenshot) ─────────────────────────────
   Background: deep dark-purple #0a0514
   Primary accent: bright purple #a855f7 / #7c3aed
   Gradient text: from purple → cyan  
   Card surface: #150a2a                                                  */

/* ─── Content ─────────────────────────────────────────────────────────── */

const TRANSCRIPT = [
  { speaker: "Alex", time: "10:15", text: "Let's review the new product roadmap and align on our Q2 goals." },
  { speaker: "Priya", time: "10:16", text: "I think we should prioritize the AI features based on user feedback." },
] as const;

const HINDI_TRANSLATION = "मेरा मानना है कि हमें उपयोगकर्ता की प्रतिक्रिया के आधार पर AI सुविधाओं को प्राथमिकता देनी चाहिए।";

const FEATURES = [
  [Mic, "Real-time Transcription", "Accurate live transcripts with speaker detection."],
  [Globe, "200+ Language Translation", "Real-time translations so everyone can understand."],
  [BrainCircuit, "AI Summaries", "Instant summaries, key points, and action items."],
  [Search, "Smart Search", "Search across meetings, transcripts, and documents."],
  [ShieldCheck, "Enterprise Security", "End-to-end encryption and compliance you can trust."],
] as const;

const WORKFLOW = [
  "Audio Captured",
  "Speech Recognized",
  "Speaker Identified",
  "Translated",
  "AI Understood",
  "Summary Generated",
] as const;

const FAQS = [
  ["Does this join my meeting as a bot?", "No. Everything runs locally on your device. No bot sits in the call, and nothing announces itself to other participants."],
  ["How many languages are supported?", "The self-hosted translation engine (NLLB-200) supports 200+ languages. Each participant selects their own — captions update in that language without affecting anyone else."],
  ["Can the AI engine run on my own servers?", "Yes — the entire AI pipeline (speech, translation, LLM, embeddings) runs as a self-hosted service. On Enterprise, nothing has to leave your infrastructure."],
  ["What happens if the AI service is temporarily down?", "Requests automatically fall back to a configured backup provider so the product keeps working, not just fails silently."],
] as const;

/* ─── Participant card component ─────────────────────────────────────── */

const PARTICIPANTS = [
  { name: "Alex", color: "#6d28d9", accent: "#a78bfa", initials: "AX" },
  { name: "Priya", color: "#0e7490", accent: "#22d3ee", initials: "PR" },
  { name: "Rohan", color: "#065f46", accent: "#34d399", initials: "RO" },
  { name: "Meera", color: "#9d174d", accent: "#f472b6", initials: "ME" },
] as const;

function ParticipantTile({
  p,
  isActive,
  idx,
}: {
  p: (typeof PARTICIPANTS)[number];
  isActive: boolean;
  idx: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={cn(
        "relative overflow-hidden rounded-xl border transition-all duration-300",
        isActive ? "border-purple-400/60" : "border-white/[0.08]"
      )}
      style={{ background: `linear-gradient(135deg, ${p.color}40 0%, #0a0514 100%)` }}
      initial={reduce ? undefined : { opacity: 0, scale: 0.92 }}
      animate={reduce ? undefined : { opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay: idx * 0.07 }}
    >
      {/* glow ring when active */}
      {isActive && !reduce && (
        <motion.div
          className="pointer-events-none absolute inset-0 rounded-xl"
          style={{ boxShadow: `inset 0 0 0 2px ${p.accent}60, 0 0 24px ${p.accent}30` }}
          animate={{ opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 1.6, repeat: Infinity }}
        />
      )}

      {/* avatar */}
      <div className="flex h-24 items-center justify-center sm:h-32">
        <div
          className="grid h-14 w-14 place-items-center rounded-full text-lg font-semibold text-white shadow-lg sm:h-16 sm:w-16"
          style={{ background: `linear-gradient(135deg, ${p.color} 0%, ${p.accent} 100%)` }}
        >
          {p.initials}
        </div>
      </div>

      {/* name + mic indicator */}
      <div className="flex items-center justify-between px-3 pb-2.5">
        <div className="flex items-center gap-1.5">
          {isActive && !reduce && (
            <motion.span
              className="inline-block h-1.5 w-1.5 rounded-full bg-jade"
              animate={{ scale: [1, 1.6, 1] }}
              transition={{ duration: 0.7, repeat: Infinity }}
            />
          )}
          <span className="text-xs font-medium text-white/85">{p.name}</span>
        </div>
        {isActive && (
          <AudioLines className="h-3.5 w-3.5 text-jade" />
        )}
      </div>
    </motion.div>
  );
}

/* ─── Animated meeting mockup ────────────────────────────────────────── */

function MeetingMockup() {
  const reduce = useReducedMotion();
  const [activeSpeaker, setActiveSpeaker] = useState(0);
  const [showTranslation, setShowTranslation] = useState(false);
  const [typedText, setTypedText] = useState("");
  const [step, setStep] = useState(0); // 0=speaker0, 1=speaker1+translate, 2=repeat
  const target = TRANSCRIPT[1].text;

  useEffect(() => {
    if (reduce) {
      setTypedText(target);
      setShowTranslation(true);
      return;
    }
    let cancelled = false;
    const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

    async function loop() {
      while (!cancelled) {
        setActiveSpeaker(0);
        setTypedText("");
        setShowTranslation(false);
        await sleep(2200);
        if (cancelled) return;

        setActiveSpeaker(1);
        // type the text
        for (let i = 1; i <= target.length; i++) {
          if (cancelled) return;
          setTypedText(target.slice(0, i));
          await sleep(28);
        }
        await sleep(400);
        if (cancelled) return;
        setShowTranslation(true);
        await sleep(3600);
      }
    }
    loop();
    return () => { cancelled = true; };
  }, [reduce, target]);

  return (
    <div
      className="overflow-hidden rounded-2xl border border-white/[0.1]"
      style={{ background: "#0d0620", boxShadow: "0 24px 80px rgba(139,31,199,.28)" }}
    >
      {/* header bar */}
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.08] px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-medium text-white/80">
          <span className="flex h-6 items-center gap-1.5 rounded-full border border-red-400/40 bg-red-500/20 px-2 text-[11px] font-semibold text-red-400">
            <span className="h-1.5 w-1.5 rounded-full bg-red-400" /> LIVE
          </span>
          Product Strategy Meeting
        </div>
        <div className="flex -space-x-1.5">
          {PARTICIPANTS.map((p) => (
            <div
              key={p.name}
              className="grid h-6 w-6 place-items-center rounded-full border border-white/20 text-[9px] font-bold text-white"
              style={{ background: `linear-gradient(135deg, ${p.color}, ${p.accent})` }}
            >
              {p.initials[0]}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-0 sm:flex-row">
        {/* participant grid */}
        <div className="grid grid-cols-2 gap-2 p-3 sm:w-[55%]">
          {PARTICIPANTS.map((p, idx) => (
            <ParticipantTile key={p.name} p={p} isActive={activeSpeaker === idx} idx={idx} />
          ))}
        </div>

        {/* transcript + translation panel */}
        <div className="flex flex-1 flex-col border-t border-white/[0.08] p-3 sm:border-l sm:border-t-0">
          <div className="mb-2 flex gap-2 text-xs">
            {["Transcript", "AI Summary", "Chat"].map((tab) => (
              <button
                key={tab}
                className={cn(
                  "rounded-md px-2 py-1 transition",
                  tab === "Transcript"
                    ? "bg-purple-600/30 font-medium text-white"
                    : "text-white/45 hover:text-white/70"
                )}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="flex-1 space-y-3 overflow-hidden">
            {/* static first line */}
            <div className="flex items-start gap-2">
              <div className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#6d28d9] text-[9px] font-bold text-white">
                AX
              </div>
              <div>
                <p className="text-[10px] text-white/40">Alex · 10:15</p>
                <p className="text-xs leading-5 text-white/80">{TRANSCRIPT[0].text}</p>
              </div>
            </div>

            {/* animated second line */}
            <div className="flex items-start gap-2">
              <div className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#0e7490] text-[9px] font-bold text-white">
                PR
              </div>
              <div className="flex-1">
                <p className="text-[10px] text-white/40">Priya · 10:16</p>
                <p className="min-h-[2.5rem] text-xs leading-5 text-white/80">
                  {typedText}
                  {typedText.length < target.length && !reduce && (
                    <span className="ml-0.5 inline-block h-3 w-0.5 translate-y-[1px] animate-pulse bg-purple-400" />
                  )}
                </p>
              </div>
            </div>

            {/* live translation */}
            <AnimatePresence>
              {showTranslation && (
                <motion.div
                  initial={reduce ? undefined : { opacity: 0, y: 8 }}
                  animate={reduce ? undefined : { opacity: 1, y: 0 }}
                  exit={reduce ? undefined : { opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="rounded-lg border border-purple-500/30 bg-purple-500/10 p-2.5"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <div className="flex items-center gap-1 text-[10px] font-medium text-purple-300">
                      <Languages className="h-3 w-3" /> Hindi
                    </div>
                    <span className="flex items-center gap-1 text-[9px] text-jade">
                      <span className="h-1 w-1 animate-pulse rounded-full bg-jade" />
                      Live Translation Active
                    </span>
                  </div>
                  <p className="text-[11px] leading-5 text-white/80">{HINDI_TRANSLATION}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* bottom controls */}
      <div className="flex items-center justify-center gap-3 border-t border-white/[0.08] py-3">
        {[Mic, "video", "share", "grid", Users, "end"].map((icon, i) => {
          if (icon === "end") {
            return (
              <button key={i} className="grid h-9 w-9 place-items-center rounded-full bg-red-500 text-white" aria-label="End call">
                <span className="text-base">✕</span>
              </button>
            );
          }
          if (icon === "video") {
            return (
              <button key={i} className="grid h-9 w-9 place-items-center rounded-full border border-white/15 bg-white/8 text-white/70" aria-label="Camera">
                <span className="text-sm">⬛</span>
              </button>
            );
          }
          if (typeof icon === "string") {
            return (
              <button key={i} className="grid h-9 w-9 place-items-center rounded-full border border-white/15 bg-white/8 text-white/70" aria-label={icon}>
                <span className="text-sm">⬛</span>
              </button>
            );
          }
          const Icon = icon as React.ElementType;
          return (
            <button key={i} className="grid h-9 w-9 place-items-center rounded-full border border-white/15 bg-white/8 text-white/70 hover:border-purple-400/40 hover:text-white" aria-label="Mic">
              <Icon className="h-4 w-4" />
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Reveal wrapper ─────────────────────────────────────────────────── */

function Reveal({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? undefined : { opacity: 0, y: 20 }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

/* ─── FAQ item ───────────────────────────────────────────────────────── */

function Faq({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-white/[0.09] bg-white/[0.03]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-medium text-white/90"
      >
        {q}
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-white/40 transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.24 }}
            className="overflow-hidden"
          >
            <p className="px-5 pb-4 text-sm leading-6 text-white/55">{a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─── Page ───────────────────────────────────────────────────────────── */

export default function LandingPage() {
  const reduce = useReducedMotion();
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setActiveStep((v) => (v + 1) % WORKFLOW.length), 900);
    return () => clearInterval(id);
  }, [reduce]);

  return (
    <main className="min-h-screen overflow-x-hidden text-white" style={{ background: "#0a0514" }}>
      {/* ambient glows */}
      {!reduce && (
        <>
          <motion.div
            aria-hidden
            className="pointer-events-none fixed left-0 top-0 -z-0 h-[50vh] w-[50vw] rounded-full"
            style={{ background: "radial-gradient(circle, rgba(109,40,217,.18) 0%, transparent 70%)", filter: "blur(40px)" }}
            animate={{ x: [0, 40, 0], y: [0, 30, 0] }}
            transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            aria-hidden
            className="pointer-events-none fixed right-0 top-1/3 -z-0 h-[40vh] w-[40vw] rounded-full"
            style={{ background: "radial-gradient(circle, rgba(6,182,212,.1) 0%, transparent 70%)", filter: "blur(60px)" }}
            animate={{ x: [0, -30, 0], y: [0, -20, 0] }}
            transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
          />
        </>
      )}

      {/* ── Nav ── */}
      <nav className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#0a0514]/80 backdrop-blur-2xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-3 font-semibold text-white">
            <Image src="/brand/icon-mark.png" alt="" width={36} height={36} className="h-9 w-9" />
            <span>Microtechnique AI</span>
          </Link>
          <div className="hidden items-center gap-6 text-sm text-white/55 md:flex">
            <a href="#features" className="hover:text-white">Features</a>
            <a href="#workflow" className="hover:text-white">How it works</a>
            <a href="#translate" className="hover:text-white">Translation</a>
            <a href="#pricing" className="hover:text-white">Pricing</a>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/login" className="px-4 py-2 text-sm text-white/70 hover:text-white">Log in</Link>
            <Link
              href="/dashboard"
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-gradient-to-r from-[#7c3aed] to-[#a855f7] px-4 text-sm font-semibold text-white transition hover:brightness-110"
            >
              Get Started Free <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative px-4 pb-16 pt-14 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl items-center gap-10 lg:grid-cols-[1fr_1.1fr]">
          <div>
            <Reveal>
              <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-sm font-medium text-purple-300">
                <Sparkles className="h-4 w-4" /> AI-Powered Meeting Assistant
              </p>
            </Reveal>
            <Reveal delay={0.06}>
              <h1 className="max-w-xl text-5xl font-bold leading-[1.07] sm:text-6xl">
                <span
                  style={{
                    background: "linear-gradient(135deg, #fff 0%, #d8b4fe 40%, #818cf8 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    backgroundClip: "text",
                  }}
                >
                  Meet Smarter.
                </span>
                <br />
                <span
                  style={{
                    background: "linear-gradient(135deg, #a78bfa 0%, #60a5fa 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    backgroundClip: "text",
                  }}
                >
                  Collaborate Better.
                </span>
              </h1>
            </Reveal>
            <Reveal delay={0.12}>
              <p className="mt-5 max-w-lg text-lg leading-8 text-white/60">
                Real-time transcription, translation in 200+ languages, AI summaries, and
                actionable insights — all in one intelligent meeting platform.
              </p>
            </Reveal>
            <Reveal delay={0.18}>
              <div className="mt-7 flex flex-wrap gap-3">
                <Link
                  href="/dashboard"
                  className="inline-flex h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-[#7c3aed] to-[#a855f7] px-6 text-sm font-semibold text-white transition hover:brightness-110"
                >
                  Start Your Free Trial <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="/live"
                  className="inline-flex h-11 items-center gap-2 rounded-xl border border-white/15 bg-white/[0.06] px-6 text-sm font-medium text-white/85 transition hover:bg-white/[0.1]"
                >
                  <Zap className="h-4 w-4 text-jade" /> Try Live Meeting
                </Link>
              </div>
            </Reveal>
            <Reveal delay={0.24}>
              <div className="mt-8 flex flex-wrap items-center gap-4 text-sm text-white/50">
                {[
                  [Mic, "Real-time AI"],
                  [Languages, "200+ Languages"],
                  [ShieldCheck, "Enterprise Security"],
                ].map(([Icon, label]) => {
                  const I = Icon as React.ElementType;
                  return (
                    <span key={String(label)} className="flex items-center gap-1.5">
                      <I className="h-4 w-4 text-purple-400" /> {String(label)}
                    </span>
                  );
                })}
              </div>
            </Reveal>
          </div>

          <Reveal delay={0.1}>
            <MeetingMockup />
          </Reveal>
        </div>
      </section>

      {/* ── Features grid ── */}
      <section id="features" className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Reveal>
            <h2 className="text-center text-3xl font-bold text-white sm:text-4xl">
              Everything you need for powerful meetings
            </h2>
            <p className="mt-3 text-center text-white/55">
              AI that listens, understands, and helps you achieve more.
            </p>
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {FEATURES.map(([Icon, title, text], i) => (
              <Reveal key={title} delay={i * 0.06}>
                <div className="flex h-full flex-col rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5 transition hover:border-purple-500/40 hover:bg-purple-500/[0.05]">
                  <div className="mb-4 grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-[#7c3aed] to-[#a855f7]">
                    <Icon className="h-5 w-5 text-white" />
                  </div>
                  <h3 className="mb-2 font-semibold text-white">{title}</h3>
                  <p className="text-sm leading-6 text-white/55">{text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── AI Workflow ── */}
      <section id="workflow" className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Reveal>
            <p className="text-center text-sm font-medium uppercase tracking-wider text-purple-400">AI Pipeline</p>
            <h2 className="mt-2 text-center text-3xl font-bold text-white">
              From your voice to actionable intelligence
            </h2>
          </Reveal>
          <div className="mt-10 flex flex-col items-center gap-2 sm:flex-row sm:items-start sm:justify-center sm:gap-0">
            {WORKFLOW.map((step, i) => (
              <div key={step} className="flex items-center">
                <motion.div
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-xl border px-4 py-3 text-center transition-all duration-300",
                    activeStep === i || reduce
                      ? "border-purple-500/50 bg-purple-500/15 text-white"
                      : "border-white/[0.08] bg-white/[0.03] text-white/50"
                  )}
                  animate={activeStep === i && !reduce ? { scale: [1, 1.04, 1] } : { scale: 1 }}
                  transition={{ duration: 0.6 }}
                >
                  <span className="text-[10px] font-medium uppercase tracking-wider text-purple-400/80">0{i + 1}</span>
                  <span className="text-sm font-medium">{step}</span>
                </motion.div>
                {i < WORKFLOW.length - 1 && (
                  <div className="mx-1 hidden h-px w-6 bg-gradient-to-r from-purple-500/40 to-purple-500/10 sm:block" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Live translation demo ── */}
      <section id="translate" className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
            <Reveal>
              <p className="text-sm font-medium uppercase tracking-wider text-purple-400">Live Translation</p>
              <h2 className="mt-2 text-3xl font-bold text-white">
                <Languages className="mb-2 inline-block h-8 w-8 text-purple-400" />{" "}
                One meeting, every language
              </h2>
              <p className="mt-4 leading-7 text-white/60">
                Each participant selects their own language. Real-time captions update
                continuously — without interrupting the meeting or anyone else&apos;s view.
              </p>
              <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
                {[
                  ["🇬🇧 English", "Host", "purple"],
                  ["🇮🇳 Hindi", "Participant A", "blue"],
                  ["🇫🇷 French", "Participant B", "green"],
                  ["🇯🇵 Japanese", "Participant C", "pink"],
                  ["🇸🇦 Arabic", "Participant D", "orange"],
                  ["🇪🇸 Spanish", "Participant E", "cyan"],
                ].map(([lang, role]) => (
                  <div key={String(lang)} className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2">
                    <span className="text-base">{String(lang).split(" ")[0]}</span>
                    <div>
                      <p className="font-medium text-white/90">{String(lang).split(" ").slice(1).join(" ")}</p>
                      <p className="text-[11px] text-white/40">{String(role)}</p>
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-sm text-white/40">+ 194 more languages via self-hosted NLLB-200</p>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
                <p className="mb-2 text-xs text-white/40">Original (English)</p>
                <p className="mb-4 rounded-lg border border-white/[0.1] bg-white/[0.05] px-4 py-3 text-sm text-white/85">
                  &ldquo;Let&apos;s lock the Q3 budget by Friday.&rdquo;
                </p>
                <p className="mb-2 text-xs text-white/40">Live captions — simultaneously</p>
                <div className="space-y-2">
                  {[
                    ["🇮🇳", "Hindi", "हमें Q3 बजट शुक्रवार तक तय करना है।"],
                    ["🇯🇵", "Japanese", "Q3予算は金曜までに確定させましょう。"],
                    ["🇫🇷", "French", "Verrouillons le budget T3 avant vendredi."],
                    ["🇸🇦", "Arabic", "لنحدد ميزانية الربع الثالث بحلول الجمعة."],
                  ].map(([flag, lang, text]) => (
                    <div key={String(lang)} className="flex items-start gap-2.5 rounded-lg border border-purple-500/20 bg-purple-500/10 px-3 py-2.5 text-sm">
                      <span>{String(flag)}</span>
                      <div>
                        <span className="text-[10px] text-purple-300">{String(lang)} · </span>
                        <span className="text-white/80">{String(text)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Architecture ── */}
      <section className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Reveal>
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-8 sm:p-10">
              <Server className="mb-5 h-7 w-7 text-purple-400" />
              <h2 className="text-3xl font-bold text-white">Your AI, on your infrastructure</h2>
              <p className="mt-3 max-w-2xl leading-7 text-white/55">
                The entire AI pipeline — speech, translation, LLM, embeddings — runs on a
                self-hosted engine your team controls. Cloud providers are the automatic
                fallback, not the default.
              </p>
              <div className="mt-7 grid gap-3 sm:grid-cols-2">
                {[
                  ["LLM", "Qwen2.5-7B — chat, summaries, structured output, function calling"],
                  ["Speech", "faster-whisper — real-time transcription, 100+ languages"],
                  ["Translation", "NLLB-200 — 200 languages, self-hosted neural translation"],
                  ["Embeddings", "sentence-transformers — semantic search over your knowledge base"],
                ].map(([name, desc]) => (
                  <div key={String(name)} className="flex items-start gap-3 rounded-xl border border-white/[0.08] bg-[#0a0514]/50 p-4">
                    <Cpu className="mt-0.5 h-4 w-4 shrink-0 text-purple-400" />
                    <div>
                      <p className="font-semibold text-white/90">{String(name)}</p>
                      <p className="mt-1 text-sm leading-5 text-white/50">{String(desc)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── Security ── */}
      <section className="px-4 py-16 sm:px-6 lg:px-8">
        <Reveal>
          <div className="mx-auto flex max-w-7xl flex-col gap-6 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-7 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-medium uppercase tracking-wider text-purple-400">Security</p>
              <h2 className="mt-2 text-3xl font-bold text-white">Local-first by design</h2>
              <p className="mt-3 max-w-2xl leading-7 text-white/55">
                The platform never joins meetings as a participant. Capture stays
                user-controlled, cloud storage is optional, and every feature runs on JWT
                auth, workspace RBAC, and audit-ready event logs.
              </p>
            </div>
            <div className="grid shrink-0 gap-2 text-sm">
              {["No meeting bot", "Workspace-level RBAC", "Optional cloud sync", "Audit-ready events"].map((item) => (
                <p key={item} className="flex items-center gap-2 text-white/75">
                  <CheckCircle2 className="h-4 w-4 text-jade" /> {item}
                </p>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Reveal>
            <h2 className="text-center text-3xl font-bold text-white">Pricing that matches real usage</h2>
          </Reveal>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {[
              ["Starter", "$19", "For solo operators", ["Live transcript & AI suggestions", "Meeting history & search", "Single workspace"]],
              ["Pro", "$49", "For high-volume teams", ["Everything in Starter", "RAG knowledge workspace", "Interview / Sales / Presentation modes", "Usage analytics & integrations"], true],
              ["Enterprise", "Custom", "For regulated orgs", ["Everything in Pro", "SSO & audit logs", "Self-hosted AI engine", "Regional data residency"]],
            ].map(([name, price, label, details, featured]: any) => (
              <Reveal key={name}>
                <div className={cn(
                  "flex h-full flex-col rounded-2xl border p-6 transition",
                  featured
                    ? "border-purple-500/50 bg-purple-500/[0.08]"
                    : "border-white/[0.08] bg-white/[0.03]"
                )}>
                  {featured && (
                    <span className="mb-3 inline-flex w-fit rounded-full bg-purple-500/20 px-2.5 py-1 text-xs font-medium text-purple-300">
                      Most teams choose this
                    </span>
                  )}
                  <p className="text-sm text-white/45">{label}</p>
                  <h3 className="mt-2 text-xl font-bold text-white">{name}</h3>
                  <p className="mt-4 text-4xl font-bold text-white">{price}</p>
                  <ul className="mt-5 flex-1 space-y-2 text-sm text-white/60">
                    {(details as string[]).map((d: string) => (
                      <li key={d} className="flex items-start gap-2">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-jade" /> {d}
                      </li>
                    ))}
                  </ul>
                  <Link
                    href="/dashboard"
                    className={cn(
                      "mt-6 inline-flex h-10 items-center justify-center rounded-xl text-sm font-medium transition",
                      featured
                        ? "bg-gradient-to-r from-[#7c3aed] to-[#a855f7] text-white hover:brightness-110"
                        : "border border-white/15 bg-white/[0.06] text-white/85 hover:bg-white/[0.1]"
                    )}
                  >
                    Choose plan
                  </Link>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl">
          <Reveal>
            <h2 className="text-center text-3xl font-bold text-white">Frequently asked</h2>
          </Reveal>
          <div className="mt-6 space-y-2">
            {FAQS.map(([q, a]) => (
              <Reveal key={q}>
                <Faq q={q} a={a} />
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="px-4 py-16 sm:px-6 lg:px-8">
        <Reveal>
          <div
            className="mx-auto max-w-7xl overflow-hidden rounded-3xl p-12 text-center"
            style={{ background: "linear-gradient(135deg, #33005C 0%, #5B0A8C 55%, #8B1FC7 100%)" }}
          >
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Stop taking meeting notes. Start running on them.
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-white/70">
              Open the workspace and see your next meeting transcribed, translated and
              summarized in real time — on AI you control.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link
                href="/dashboard"
                className="inline-flex h-11 items-center gap-2 rounded-xl bg-white px-6 text-sm font-semibold text-[#5B0A8C] transition hover:brightness-105"
              >
                Get Started Free <Zap className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/[0.08] px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 text-sm text-white/40 sm:flex-row">
          <div className="flex items-center gap-2">
            <Image src="/brand/icon-mark.png" alt="" width={24} height={24} className="h-6 w-6 opacity-70" />
            Microtechnique AI Meeting
          </div>
          <div className="flex items-center gap-5">
            <a href="#features" className="hover:text-white/70">Features</a>
            <a href="#pricing" className="hover:text-white/70">Pricing</a>
            <a href="#faq" className="hover:text-white/70">FAQ</a>
            <Link href="/login" className="hover:text-white/70">Sign in</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
