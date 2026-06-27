import Link from "next/link";
import Image from "next/image";
import { ArrowRight, AudioLines, BarChart3, BrainCircuit, CheckCircle2, DatabaseZap, FileSearch, LockKeyhole, MessageSquareText, RadioTower, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { Button } from "@/components/button";
import { LiveMeeting } from "@/components/live-meeting";

const features = [
  [RadioTower, "Passive audio capture", "Zoom, Meet, Teams, Webex and huddles through system, ambient or hybrid capture."],
  [MessageSquareText, "Auto question detection", "Technical questions, objections, clarifications and interview prompts are detected without a manual trigger."],
  [DatabaseZap, "Private context retrieval", "Meeting memory and uploaded docs are searched before every response."],
  [BarChart3, "Meeting intelligence", "Summaries, decisions, risks, action items and sentiment are generated while the meeting is still live."]
] as const;

const workflow = ["Listen", "Transcribe", "Detect", "Retrieve", "Respond", "Summarize"];
const modes = ["Meeting", "Interview", "Sales", "Presentation"];
const plans = [
  ["Starter", "$19", "For solo operators", "Live transcript, AI suggestions, meeting history"],
  ["Pro", "$49", "For high-volume teams", "RAG workspace, premium modes, analytics, integrations"],
  ["Enterprise", "Custom", "For regulated orgs", "SSO, audit logs, retention, regional storage"]
] as const;

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[linear-gradient(180deg,#fbfcfd_0%,#eef2f5_45%,#f8fafb_100%)] text-ink">
      <nav className="sticky top-0 z-30 border-b border-ink/10 bg-white/78 backdrop-blur-2xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-3 font-semibold">
            <Image src="/brand/icon-mark.png" alt="" width={40} height={40} className="h-10 w-10" />
            <span>Microtechnique AI Meeting</span>
          </Link>
          <div className="hidden items-center gap-6 text-sm text-ink/62 md:flex">
            <a href="#workspace" className="hover:text-ink">Workspace</a>
            <a href="#features" className="hover:text-ink">Features</a>
            <a href="#pricing" className="hover:text-ink">Pricing</a>
            <a href="#security" className="hover:text-ink">Security</a>
          </div>
          <Link href="/dashboard" className="inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-medium text-white shadow-soft">
            Open app <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </nav>

      <section className="px-4 pb-12 pt-10 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[.78fr_1.22fr] lg:items-center">
          <div>
            <p className="mb-4 inline-flex items-center gap-2 rounded-md border border-jade/30 bg-jade/10 px-3 py-1 text-sm font-medium"><Sparkles className="h-4 w-4" />Your Real-Time AI Meeting Copilot</p>
            <h1 className="max-w-3xl text-5xl font-semibold leading-tight sm:text-6xl">Transform Every Meeting into Action.ss</h1>
            <p className="mt-5 max-w-xl text-lg leading-8 text-ink/64"> Microtechnique AI combines real-time transcription, AI meeting assistance,
  multilingual translation, knowledge search, meeting summaries, analytics,
  and enterprise-grade security in one intelligent workspace.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a href="#workspace"><Button>See live workspace <Zap className="h-4 w-4" /></Button></a>
              <Link href="/live"><Button className="bg-white text-ink">Open full meeting</Button></Link>
            </div>
            <div className="mt-8 grid max-w-lg grid-cols-3 gap-3">
              {["<2s transcript", "<5s answer", "Local-first"].map((metric) => (
                <div key={metric} className="rounded-lg border border-ink/10 bg-white/72 p-3 shadow-soft backdrop-blur-xl">
                  <p className="text-sm font-semibold">{metric}</p>
                  <p className="mt-1 text-xs text-ink/50">production target</p>
                </div>
              ))}
            </div>
          </div>

          <div id="workspace" className="rounded-lg border border-ink/10 bg-white/72 p-2 shadow-glow backdrop-blur-2xl">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink/10 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-coral" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#f7c948]" />
                <span className="h-2.5 w-2.5 rounded-full bg-jade" />
                <span className="ml-2 text-ink/60">Microtechnique Workspace</span>
              </div>
              <div className="flex gap-2 text-xs text-ink/56">
                {modes.map((mode) => <span key={mode} className="rounded-md border border-ink/10 bg-white px-2.5 py-1">{mode}</span>)}
              </div>
            </div>
            <LiveMeeting compact />
          </div>
        </div>
      </section>

      <section id="features" className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-medium uppercase tracking-wide text-ink/45">Product System</p>
              <h2 className="mt-2 text-3xl font-semibold">Everything feels like one app</h2>
            </div>
            <Link href="/knowledge" className="inline-flex items-center gap-2 text-sm font-medium">Knowledge base <ArrowRight className="h-4 w-4" /></Link>
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            {features.map(([Icon, title, text]) => (
              <div key={title} className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft transition hover:-translate-y-1 hover:shadow-glow">
                <Icon className="mb-5 h-5 w-5 text-iris" />
                <h3 className="mb-2 font-semibold">{title}</h3>
                <p className="text-sm leading-6 text-ink/62">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[.9fr_1.1fr]">
          <div className="rounded-lg border border-ink/10 bg-ink p-7 text-white shadow-soft">
            <AudioLines className="mb-6 h-6 w-6 text-jade" />
            <h2 className="text-3xl font-semibold">AI agent workflow</h2>
            <p className="mt-3 leading-7 text-white/62">Question detection, context, retrieval, generation, summaries and action items run as a coordinated real-time pipeline.</p>
            <div className="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {workflow.map((step, index) => <div key={step} className="rounded-md border border-white/10 bg-white/8 p-3"><p className="text-xs text-white/45">0{index + 1}</p><p className="mt-1 font-medium">{step}</p></div>)}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              [BrainCircuit, "Interview mode", "STAR answers, coding hints and behavioral response framing."],
              [FileSearch, "Sales mode", "Objection handling, discovery questions and closing statements."],
              [ShieldCheck, "Presentation mode", "Speaker notes, audience question responses and talk insights."],
              [LockKeyhole, "Meeting mode", "Key decisions, risks, action items and post-call summaries."]
            ].map(([Icon, title, text]) => (
              <div key={String(title)} className="rounded-lg border border-ink/10 bg-white p-5 shadow-soft">
                <Icon className="mb-5 h-5 w-5 text-jade" />
                <h3 className="font-semibold">{String(title)}</h3>
                <p className="mt-2 text-sm leading-6 text-ink/62">{String(text)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <h2 className="text-3xl font-semibold">Pricing that matches real usage</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {plans.map(([name, price, label, details]) => (
              <div key={name} className="rounded-lg border border-ink/10 bg-white p-6 shadow-soft">
                <p className="text-sm text-ink/50">{label}</p>
                <h3 className="mt-2 text-xl font-semibold">{name}</h3>
                <p className="mt-4 text-4xl font-semibold">{price}</p>
                <p className="mt-4 text-sm leading-6 text-ink/62">{details}</p>
                <Button className="mt-6 w-full bg-white text-ink">Choose plan</Button>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="security" className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 rounded-lg border border-ink/10 bg-white p-7 shadow-soft md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-wide text-ink/45">Security</p>
            <h2 className="mt-2 text-3xl font-semibold">Local-first by design</h2>
            <p className="mt-3 max-w-3xl leading-7 text-ink/62">The app never joins meetings. Capture remains user-controlled, cloud storage is optional, and the architecture includes JWT, RBAC, encryption-ready data models, audit logs and retention policy hooks.</p>
          </div>
          <div className="grid gap-2 text-sm">
            {["No meeting bot", "Optional cloud sync", "Audit-ready events"].map((item) => <p key={item} className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-jade" />{item}</p>)}
          </div>
        </div>
      </section>
    </main>
  );
}
