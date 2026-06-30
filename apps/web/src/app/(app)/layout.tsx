"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { useAuthStore } from "@/store/auth-store";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const hydrated = useAuthStore((s) => s.hydrated);

  useEffect(() => {
    if (hydrated && !token) router.replace("/login");
  }, [hydrated, token, router]);

  if (!hydrated) return null; // avoid a flash of protected content before we know auth state
  if (!token) return null; // redirecting

  return <AppShell>{children}</AppShell>;
}
