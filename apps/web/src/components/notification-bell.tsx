"use client";
import { useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { api, type NotificationOut } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

export function NotificationBell() {
  const token = useAuthStore((s) => s.token);
  const [notifications, setNotifications] = useState<NotificationOut[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!token) return;
    const load = () => api.listNotifications(token).then(setNotifications).catch(() => {});
    load();
    // Simple polling, not a push system — there's no server-push infra wired for
    // notifications (no SSE/websocket broadcast channel for this), so this is an honest
    // "check every 30s" rather than claiming real-time delivery it doesn't have.
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [token]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  async function handleOpen() {
    setOpen((v) => !v);
  }

  async function handleMarkAllRead() {
    if (!token) return;
    await api.markAllNotificationsRead(token);
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }

  async function handleMarkRead(id: string) {
    if (!token) return;
    await api.markNotificationRead(token, id);
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
  }

  return (
    <div className="relative">
      <button onClick={handleOpen} className="relative grid h-9 w-9 place-items-center rounded-md hover:bg-ink/5">
        <Bell className="h-5 w-5 text-ink/60" />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-coral px-1 text-[10px] font-medium text-white">
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-20 w-80 rounded-lg border border-ink/10 bg-white shadow-glow">
          <div className="flex items-center justify-between border-b border-ink/8 p-3">
            <span className="text-sm font-medium">Notifications</span>
            {unreadCount > 0 && (
              <button onClick={handleMarkAllRead} className="text-xs text-iris hover:underline">
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {notifications.length === 0 && <p className="p-4 text-sm text-ink/45">No notifications yet.</p>}
            {notifications.map((n) => (
              <button
                key={n.id}
                onClick={() => handleMarkRead(n.id)}
                className={`block w-full border-b border-ink/8 p-3 text-left text-sm last:border-b-0 hover:bg-mist ${
                  n.read ? "text-ink/50" : "font-medium text-ink"
                }`}
              >
                {n.message}
                <span className="mt-1 block text-xs text-ink/40">{new Date(n.created_at).toLocaleString()}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
