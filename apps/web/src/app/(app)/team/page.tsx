"use client";
import { useEffect, useState } from "react";
import { CheckCircle2, Crown, ShieldCheck, Trash2, UserPlus, Users } from "lucide-react";
import { Button } from "@/components/button";
import { api, ApiError, NetworkError, type ActionItemEntry, type MembershipOut, type WorkspaceOut } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

const ROLE_ICON = { owner: Crown, admin: ShieldCheck, member: Users } as const;

export default function TeamPage() {
  const token = useAuthStore((s) => s.token);
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[] | null>(null);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceOut | null>(null);
  const [members, setMembers] = useState<MembershipOut[]>([]);
  const [actionItems, setActionItems] = useState<ActionItemEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .listWorkspaces(token)
      .then((ws) => {
        setWorkspaces(ws);
        if (ws.length > 0) setActiveWorkspace(ws[0]);
      })
      .catch((err) => setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not load workspaces."))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token || !activeWorkspace) return;
    api.listMembers(token, activeWorkspace.id).then(setMembers).catch(() => setMembers([]));
    api.getTeamActionBoard(token, activeWorkspace.id).then(setActionItems).catch(() => setActionItems([]));
  }, [token, activeWorkspace]);

  const canManage = activeWorkspace?.my_role === "owner" || activeWorkspace?.my_role === "admin";

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !activeWorkspace || !inviteEmail.trim()) return;
    setInviting(true);
    setInviteError(null);
    try {
      const member = await api.addMember(token, activeWorkspace.id, inviteEmail.trim());
      setMembers((prev) => [...prev, member]);
      setInviteEmail("");
    } catch (err) {
      // Most likely cause: that email hasn't registered an account yet — there's no
      // email-invite system, so adding someone requires them to sign up first.
      setInviteError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not add member.");
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(userId: string, role: string) {
    if (!token || !activeWorkspace) return;
    try {
      const updated = await api.updateMemberRole(token, activeWorkspace.id, userId, role);
      setMembers((prev) => prev.map((m) => (m.user_id === userId ? updated : m)));
    } catch (err) {
      setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not update role.");
    }
  }

  async function handleRemove(userId: string) {
    if (!token || !activeWorkspace) return;
    try {
      await api.removeMember(token, activeWorkspace.id, userId);
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
    } catch (err) {
      setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not remove member.");
    }
  }

  if (loading) return <section className="p-6 text-ink/55">Loading…</section>;

  return (
    <section className="p-6">
      <h1 className="mb-1 text-2xl font-semibold">Team</h1>
      <p className="mb-6 text-sm text-ink/55">Workspace members, roles, and action items across every meeting.</p>

      {error && <p className="mb-4 text-sm text-coral">{error}</p>}

      {workspaces && workspaces.length > 1 && (
        <div className="mb-6 flex gap-2">
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              onClick={() => setActiveWorkspace(ws)}
              className={`rounded-md border px-3 py-1.5 text-sm ${
                activeWorkspace?.id === ws.id ? "border-iris bg-iris/5 text-iris" : "border-ink/15 text-ink/60"
              }`}
            >
              {ws.name}
            </button>
          ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <div className="rounded-lg border border-ink/10 bg-white shadow-soft">
          <div className="flex items-center justify-between border-b border-ink/8 p-4">
            <h2 className="font-semibold">Members</h2>
            <span className="text-xs text-ink/45">{activeWorkspace?.name}</span>
          </div>

          {canManage && (
            <form onSubmit={handleInvite} className="flex gap-2 border-b border-ink/8 p-4">
              <input
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="teammate@company.com"
                type="email"
                className="flex-1 rounded-md border border-ink/15 px-3 py-2 text-sm"
              />
              <Button type="submit" disabled={inviting} className="h-9 px-3 text-sm">
                <UserPlus className="h-4 w-4" />
                {inviting ? "Adding…" : "Add"}
              </Button>
            </form>
          )}
          {inviteError && <p className="border-b border-ink/8 p-3 text-sm text-coral">{inviteError}</p>}

          {members.map((m) => {
            const RoleIcon = ROLE_ICON[m.role];
            return (
              <div key={m.user_id} className="flex items-center justify-between border-b border-ink/8 p-4 last:border-b-0">
                <div>
                  <p className="font-medium">{m.full_name || m.email}</p>
                  <p className="text-xs text-ink/50">{m.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  {canManage && m.role !== "owner" ? (
                    <select
                      value={m.role}
                      onChange={(e) => handleRoleChange(m.user_id, e.target.value)}
                      className="rounded-md border border-ink/15 px-2 py-1 text-xs"
                    >
                      <option value="member">member</option>
                      <option value="admin">admin</option>
                    </select>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs text-ink/55">
                      <RoleIcon className="h-3.5 w-3.5" />
                      {m.role}
                    </span>
                  )}
                  {canManage && m.role !== "owner" && (
                    <button onClick={() => handleRemove(m.user_id)} className="text-ink/30 hover:text-coral">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="rounded-lg border border-ink/10 bg-white shadow-soft">
          <div className="border-b border-ink/8 p-4">
            <h2 className="font-semibold">Team Action Board</h2>
            <p className="mt-1 text-xs text-ink/45">Every action item detected across this workspace's meetings.</p>
          </div>
          {actionItems.length === 0 && <p className="p-4 text-sm text-ink/45">No action items yet.</p>}
          {actionItems.map((item, i) => (
            <div key={i} className="flex items-start gap-2 border-b border-ink/8 p-3 last:border-b-0">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-iris" />
              <div>
                <p className="text-sm text-ink/72">{item.text}</p>
                <p className="text-xs text-ink/40">{item.meeting_title}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
