"use client";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { BarChart3, CreditCard, FileAudio2, FolderSearch, History, LayoutDashboard, LogOut, Plug, Search, Settings, ShieldCheck, UserCircle, Users, Video } from "lucide-react";
import { NotificationBell } from "@/components/notification-bell";
import { useAuthStore } from "@/store/auth-store";
const nav = [["Dashboard","/dashboard",LayoutDashboard],["Live","/live",FileAudio2],["Rooms","/rooms",Video],["Library","/history",History],["Knowledge","/knowledge",FolderSearch],["Search","/search",Search],["Team","/team",Users],["Analytics","/analytics",BarChart3],["Integrations","/integrations",Plug],["Admin","/admin",ShieldCheck],["Settings","/settings",Settings],["Billing","/billing",CreditCard],["Profile","/profile",UserCircle]] as const;
export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  return (
    <div className="min-h-screen bg-mist">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-ink/10 bg-white/72 p-4 backdrop-blur-xl lg:flex lg:flex-col">
        <Link href="/" className="mb-8 flex items-center gap-3 px-2 py-3 font-semibold">
          <Image src="/brand/icon-mark.png" alt="" width={36} height={36} className="h-9 w-9" />
          <span>Microtechnique AI Meeting</span>
        </Link>
        <nav className="flex-1 space-y-1">
          {nav.map(([label, href, Icon]) => (
            <Link key={href} href={href} className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-ink/72 transition hover:bg-ink/5 hover:text-ink">
              <Icon className="h-4 w-4" /> {label}
            </Link>
          ))}
        </nav>
        <button
          onClick={() => { logout(); router.replace("/login"); }}
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-ink/55 transition hover:bg-ink/5 hover:text-ink"
        >
          <LogOut className="h-4 w-4" /> Log out
        </button>
      </aside>
      <div className="lg:pl-64">
        <header className="flex items-center justify-end border-b border-ink/8 bg-white/72 px-4 py-2 backdrop-blur-xl">
          <NotificationBell />
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
