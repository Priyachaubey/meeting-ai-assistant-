const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? window.location.origin : "");

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`
    : "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Distinct from ApiError on purpose: ApiError means the backend responded (4xx/5xx) — the
// connection itself worked. NetworkError means fetch() never got a response at all, which
// only happens for a handful of real causes: the backend isn't running, the wrong URL/port
// is configured, or CORS blocked it. Collapsing both into one generic "Something went wrong"
// message (as earlier versions of this file did) makes that distinction undiagnosable from
// the UI alone — every login/register page tracing this exact failure should catch
// NetworkError specifically and say something actionable, not generic.
export class NetworkError extends Error {
  url: string;
  constructor(url: string, cause: unknown) {
    super(
      `Could not reach the API at ${url}. Most likely causes: (1) the backend isn't running, ` +
        `(2) NEXT_PUBLIC_API_URL points to the wrong host/port, or (3) CORS is blocking this ` +
        `origin — check the browser console for a CORS error specifically vs. a connection-` +
        `refused error, they need different fixes.`
    );
    this.url = url;
    this.cause = cause;
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string | null): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.headers) Object.assign(headers, options.headers as Record<string, string>);
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const url = `${API_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, { ...options, headers });
  } catch (cause) {
    // fetch() throws (not a rejected-with-status response, an actual thrown exception) only
    // for network-level failures — connection refused, DNS failure, or a CORS-blocked
    // response. There is no HTTP status code to read here at all.
    throw new NetworkError(url, cause);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // body wasn't JSON — keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type TokenResponse = { access_token: string; token_type: string };
export type MeetingSummary = {
  meeting_id: string;
  summary: string;
  decisions: string[];
  risks: string[];
  action_items: string[];
};
export type SubscriptionOut = { plan: string; status: string; current_period_end: string | null };
export type MeetingOut = { id: string; title: string; mode: string; created_at: string; has_summary: boolean };
export type AgentResult = {
  question_detected: boolean;
  suggested_response: string | null;
  follow_ups: string[];
  action_items: string[];
  sentiment: string;
  decisions: string[];
  risks: string[];
  speaker?: string;
  text?: string;
  timestamp_ms?: number;
};
export type KnowledgeSearchResult = {
  document_id: string;
  text: string;
  score: number;
  source: "document" | "meeting";
  meeting_id: string | null;
};
export type MeetingScore = {
  overall: number;
  decisiveness: number;
  productivity: number;
  risk_penalty: number;
  note: string;
};
export type MeetingDetail = {
  meeting_id: string;
  title: string;
  mode: string;
  created_at: string;
  transcript: { speaker: string; text: string; kind: string; timestamp_ms: number }[];
  summary: string | null;
  decisions: string[];
  risks: string[];
  action_items: string[];
  follow_ups: string[];
  questions: { speaker: string; text: string; timestamp_ms: number }[];
  score: MeetingScore;
};
export type UsageSummary = {
  period_days: number;
  total_events: number;
  successful_events: number;
  failed_events: number;
  success_rate: number | null;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  by_provider: Record<string, { events: number; successes: number; prompt_tokens: number; completion_tokens: number; cost_usd: number }>;
};
export type WorkspaceOut = { id: string; name: string; created_at: string; my_role: "owner" | "admin" | "member" };
export type MembershipOut = {
  user_id: string;
  email: string;
  full_name: string | null;
  role: "owner" | "admin" | "member";
  joined_at: string;
};
export type ActionItemEntry = { meeting_id: string; meeting_title: string; text: string };
export type DocumentOut = { id: string; filename: string; content_type: string; size_bytes: number; created_at: string };
export type NotificationOut = {
  id: string;
  type: string;
  message: string;
  meeting_id: string | null;
  workspace_id: string | null;
  read: boolean;
  created_at: string;
};
export type DetailedHealth = {
  app_env: string;
  database: { ok: boolean; latency_ms?: number; error?: string };
  qdrant: { ok: boolean; latency_ms?: number; collections?: number; error?: string; url?: string };
  providers_configured: { openai: boolean; anthropic: boolean; deepgram: boolean; stripe: boolean };
};

export type UserOut = {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  audio_capture_mode: "system" | "microphone" | "hybrid";
  preferred_language: string;
  created_at: string;
};
export type ShareLinkOut = { id: string; expires_at: string; revoked: boolean; created_at: string };
export type ShareLinkCreated = ShareLinkOut & { token: string };
export type GuestMeetingView = {
  title: string;
  created_at: string;
  transcript: { speaker: string; text: string; kind: string; timestamp_ms: number }[];
  summary: string | null;
  decisions: string[];
  risks: string[];
  action_items: string[];
  follow_ups: string[];
};

export const api = {
  register: (data: { email: string; password: string; full_name?: string; workspace_name?: string }) =>
    request<TokenResponse>("/api/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (email: string, password: string) =>
    request<TokenResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),

  getProfile: (token: string) => request<UserOut>("/api/auth/me", {}, token),

  updateProfile: (token: string, payload: { full_name?: string; audio_capture_mode?: string; preferred_language?: string }) =>
    request<UserOut>("/api/auth/me", { method: "PATCH", body: JSON.stringify(payload) }, token),

  listMeetings: (token: string) => request<MeetingOut[]>("/api/meetings", {}, token),

  createMeeting: (token: string, title: string, mode = "meeting") =>
    request<{ id: string; title: string; mode: string }>(
      "/api/meetings",
      { method: "POST", body: JSON.stringify({ title, mode }) },
      token
    ),

  postTranscriptChunk: (
    token: string,
    meetingId: string,
    chunk: { speaker: string; text: string; timestamp_ms: number }
  ) =>
    request<AgentResult>(
      `/api/meetings/${meetingId}/transcript`,
      { method: "POST", body: JSON.stringify(chunk) },
      token
    ),

  getMeetingSummary: (token: string, meetingId: string) =>
    request<MeetingSummary>(`/api/meetings/${meetingId}/summary`, {}, token),

  getMeetingDetail: (token: string, meetingId: string) =>
    request<MeetingDetail>(`/api/meetings/${meetingId}/detail`, {}, token),

  generateEmailDraft: (token: string, meetingId: string) =>
    request<{ subject: string; body: string }>(
      `/api/ai/meetings/${meetingId}/email-draft`,
      { method: "POST" },
      token
    ),

  generateFollowUp: (token: string, meetingId: string) =>
    request<{ message: string }>(`/api/ai/meetings/${meetingId}/follow-up`, { method: "POST" }, token),

  askKnowledgeAssistant: (token: string, question: string) =>
    request<{ answer: string; sources: string[] }>(
      "/api/ai/ask",
      { method: "POST", body: JSON.stringify({ question }) },
      token
    ),

  translateText: (token: string, text: string, targetLanguage: string) =>
    request<{ translated_text: string; target_language: string }>(
      "/api/ai/translate",
      { method: "POST", body: JSON.stringify({ text, target_language: targetLanguage }) },
      token
    ),

  getUsageSummary: (token: string, days = 30) =>
    request<UsageSummary>(`/api/ai/usage?days=${days}`, {}, token),

  listWorkspaces: (token: string) => request<WorkspaceOut[]>("/api/workspaces", {}, token),

  createWorkspace: (token: string, name: string) =>
    request<WorkspaceOut>("/api/workspaces", { method: "POST", body: JSON.stringify({ name }) }, token),

  listMembers: (token: string, workspaceId: string) =>
    request<MembershipOut[]>(`/api/workspaces/${workspaceId}/members`, {}, token),

  addMember: (token: string, workspaceId: string, email: string, role: "admin" | "member" = "member") =>
    request<MembershipOut>(
      `/api/workspaces/${workspaceId}/members`,
      { method: "POST", body: JSON.stringify({ email, role }) },
      token
    ),

  updateMemberRole: (token: string, workspaceId: string, userId: string, role: string) =>
    request<MembershipOut>(
      `/api/workspaces/${workspaceId}/members/${userId}`,
      { method: "PATCH", body: JSON.stringify({ role }) },
      token
    ),

  removeMember: (token: string, workspaceId: string, userId: string) =>
    request<void>(`/api/workspaces/${workspaceId}/members/${userId}`, { method: "DELETE" }, token),

  getTeamActionBoard: (token: string, workspaceId: string) =>
    request<ActionItemEntry[]>(`/api/workspaces/${workspaceId}/action-items`, {}, token),

  renameWorkspace: (token: string, workspaceId: string, name: string) =>
    request<WorkspaceOut>(`/api/workspaces/${workspaceId}`, { method: "PATCH", body: JSON.stringify({ name }) }, token),

  getDetailedHealth: (token: string) => request<DetailedHealth>("/api/health/detailed", {}, token),

  listNotifications: (token: string, unreadOnly = false) =>
    request<NotificationOut[]>(`/api/notifications${unreadOnly ? "?unread_only=true" : ""}`, {}, token),

  markNotificationRead: (token: string, id: string) =>
    request<NotificationOut>(`/api/notifications/${id}/read`, { method: "PATCH" }, token),

  markAllNotificationsRead: (token: string) =>
    request<void>("/api/notifications/read-all", { method: "POST" }, token),

  createShareLink: (token: string, meetingId: string, expiresInHours = 168) =>
    request<ShareLinkCreated>(
      `/api/meetings/${meetingId}/share-links`,
      { method: "POST", body: JSON.stringify({ expires_in_hours: expiresInHours }) },
      token
    ),

  listShareLinks: (token: string, meetingId: string) =>
    request<ShareLinkOut[]>(`/api/meetings/${meetingId}/share-links`, {}, token),

  revokeShareLink: (token: string, meetingId: string, linkId: string) =>
    request<void>(`/api/meetings/${meetingId}/share-links/${linkId}`, { method: "DELETE" }, token),

  // No auth token — the share token itself is the credential. Guests have no account.
  getGuestMeeting: (shareToken: string) => request<GuestMeetingView>(`/api/guest/meetings/${shareToken}`),

  async uploadKnowledgeDocument(token: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    const url = `${API_URL}/api/knowledge/upload`;
    let res: Response;
    try {
      res = await fetch(url, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
    } catch (cause) {
      throw new NetworkError(url, cause);
    }
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return (await res.json()) as DocumentOut;
  },

  listDocuments: (token: string) => request<DocumentOut[]>("/api/knowledge/documents", {}, token),

  getDocumentDownloadUrl: (token: string, documentId: string) =>
    request<{ url: string }>(`/api/knowledge/documents/${documentId}/download-url`, {}, token),

  deleteDocument: (token: string, documentId: string) =>
    request<void>(`/api/knowledge/documents/${documentId}`, { method: "DELETE" }, token),

  searchKnowledge: (token: string, query: string) =>
    request<{ results: KnowledgeSearchResult[] }>(`/api/knowledge/search?q=${encodeURIComponent(query)}`, {}, token),

  createCheckoutSession: (token: string) =>
    request<{ checkout_url: string }>("/api/billing/checkout", { method: "POST", body: JSON.stringify({}) }, token),

  getSubscription: (token: string) => request<SubscriptionOut>("/api/billing/subscription", {}, token),

  meetingSocketUrl: (meetingId: string, token: string) =>
    `${WS_URL}/ws/meetings/${meetingId}?token=${encodeURIComponent(token)}`,

  // ── Meeting Server (real-time meeting platform, Phase 4/5 merge) ────────
  // Separate microservice (apps/meeting-server) for live multi-participant
  // rooms — distinct from the meetingSocketUrl above, which is this app's
  // existing single-user transcript socket. Falls back to localhost:8002
  // only when NEXT_PUBLIC_MEETING_SERVER_URL isn't set; set it explicitly
  // in production the same way NEXT_PUBLIC_API_URL is set.

  meetingServerUrl: (path: string) => {
    const MS_URL = process.env.NEXT_PUBLIC_MEETING_SERVER_URL || "http://localhost:8002";
    return `${MS_URL}${path}`;
  },

  meetingServerSocketUrl: (roomId: string, token: string) => {
    const MS_WS_URL = process.env.NEXT_PUBLIC_MEETING_WS_URL || "ws://localhost:8002";
    return `${MS_WS_URL}/api/meetings/ws/rooms/${roomId}?token=${encodeURIComponent(token)}`;
  },

  async meetingServerRequest<T>(path: string, options: RequestInit = {}, token?: string | null): Promise<T> {
    const url = api.meetingServerUrl(path);
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (options.headers) Object.assign(headers, options.headers as Record<string, string>);
    if (token) headers["Authorization"] = `Bearer ${token}`;

    let res: Response;
    try {
      res = await fetch(url, { ...options, headers });
    } catch (cause) {
      throw new NetworkError(url, cause);
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = (await res.json()) as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch {
        /* body wasn't JSON */
      }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  },

  createMeetingRoom: (
    token: string,
    data: { title?: string; type?: string; waiting_room?: boolean; meeting_password?: string }
  ) =>
    api.meetingServerRequest<{
      id: string;
      title: string;
      type: string;
      status: string;
      host_id: string;
      join_url: string;
      settings: Record<string, unknown>;
      created_at: string;
    }>("/api/meetings/rooms", { method: "POST", body: JSON.stringify(data) }, token),

  getMeetingRoom: (token: string, roomId: string) =>
    api.meetingServerRequest<{
      room: Record<string, unknown>;
      participants: Record<string, unknown>[];
      transcript: Record<string, unknown>[];
      ai_state: Record<string, unknown> | null;
    }>(`/api/meetings/rooms/${roomId}`, {}, token),

  joinMeetingRoom: (token: string, roomId: string, displayName: string, password?: string) =>
    api.meetingServerRequest<{ participant: Record<string, unknown>; room: Record<string, unknown>; state: string }>(
      `/api/meetings/rooms/${roomId}/join`,
      { method: "POST", body: JSON.stringify({ display_name: displayName, password }) },
      token
    ),

  leaveMeetingRoom: (token: string, roomId: string) =>
    api.meetingServerRequest<{ status: string }>(`/api/meetings/rooms/${roomId}/leave`, { method: "POST" }, token),

  // ── Waiting Room (backend already existed — never called from the frontend) ─────────────

  getWaitingList: (token: string, roomId: string) =>
    api.meetingServerRequest<{ waiting: Record<string, unknown>[] }>(`/api/meetings/rooms/${roomId}/waiting`, {}, token),

  admitFromWaiting: (token: string, roomId: string, participantId: string) =>
    api.meetingServerRequest<{ status: string; participant: Record<string, unknown> }>(
      `/api/meetings/rooms/${roomId}/waiting/admit/${participantId}`,
      { method: "POST" },
      token
    ),

  rejectFromWaiting: (token: string, roomId: string, participantId: string) =>
    api.meetingServerRequest<{ status: string }>(
      `/api/meetings/rooms/${roomId}/waiting/reject/${participantId}`,
      { method: "POST" },
      token
    ),

  sendMeetingTranscript: (
    token: string,
    roomId: string,
    data: { speaker_id?: string; speaker_name: string; text: string; kind?: string }
  ) =>
    api.meetingServerRequest<{ transcript: Record<string, unknown> }>(
      `/api/meetings/rooms/${roomId}/transcript`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  getMeetingTranscript: (token: string, roomId: string, limit = 200) =>
    api.meetingServerRequest<{ transcript: Record<string, unknown>[]; speakers: { id: string; name: string }[] }>(
      `/api/meetings/rooms/${roomId}/transcript?limit=${limit}`,
      {},
      token
    ),

  getMeetingAIState: (token: string, roomId: string) =>
    api.meetingServerRequest<{ ai_state: Record<string, unknown> | null; status: string }>(
      `/api/meetings/rooms/${roomId}/ai`,
      {},
      token
    ),

  triggerAIAnalysis: (token: string, roomId: string) =>
    api.meetingServerRequest<{ status: string; ai_state: Record<string, unknown> }>(
      `/api/meetings/rooms/${roomId}/ai/analyze`,
      { method: "POST" },
      token
    ),

  askMeetingAI: (token: string, roomId: string, question: string) =>
    api.meetingServerRequest<{ answer: string; status: string }>(
      `/api/meetings/rooms/${roomId}/ai/chat`,
      { method: "POST", body: JSON.stringify({ question }) },
      token
    ),

  generateMeetingEmail: (token: string, roomId: string) =>
    api.meetingServerRequest<{ email: string; status: string }>(
      `/api/meetings/rooms/${roomId}/ai/email`,
      { method: "POST" },
      token
    ),

  searchMeeting: (token: string, roomId: string, query: string) =>
    api.meetingServerRequest<{ results: { type: string; text: string; speaker?: string; score: number }[]; total: number }>(
      `/api/meetings/rooms/${roomId}/search?q=${encodeURIComponent(query)}`,
      {},
      token
    ),

  sendMeetingChat: (token: string, roomId: string, content: string) =>
    api.meetingServerRequest<{ message: Record<string, unknown> }>(
      `/api/meetings/rooms/${roomId}/chat`,
      { method: "POST", body: JSON.stringify({ content }) },
      token
    ),

  getMeetingChat: (token: string, roomId: string, limit = 100) =>
    api.meetingServerRequest<{ messages: Record<string, unknown>[] }>(
      `/api/meetings/rooms/${roomId}/chat?limit=${limit}`,
      {},
      token
    ),

  hostAction: (token: string, roomId: string, action: string, targetParticipantId?: string) =>
    api.meetingServerRequest<Record<string, unknown>>(
      `/api/meetings/rooms/${roomId}/host/action`,
      { method: "POST", body: JSON.stringify({ action, target_participant_id: targetParticipantId }) },
      token
    ),

  generateMeetingEmailFull: (token: string, roomId: string) =>
    api.meetingServerRequest<{ email: { subject: string; body: string; recipients: string[] }; status: string }>(
      `/api/meetings/rooms/${roomId}/email/generate`,
      { method: "POST" },
      token
    ),

  exportMeetingRoom: (token: string, roomId: string, format: "json" | "txt" | "markdown" | "html") =>
    api.meetingServerRequest<Record<string, unknown>>(`/api/meetings/rooms/${roomId}/export/${format}`, {}, token),

  setUserLanguage: (token: string, roomId: string, language: string) =>
    api.meetingServerRequest<{ status: string; language: string; room_languages: string[] }>(
      `/api/meetings/rooms/${roomId}/language`,
      { method: "POST", body: JSON.stringify({ language }) },
      token
    ),

  getRoomLanguages: (token: string, roomId: string) =>
    api.meetingServerRequest<{ languages: string[]; status: Record<string, unknown> }>(
      `/api/meetings/rooms/${roomId}/languages`,
      {},
      token
    ),

  // ── Enterprise Search (apps/api, Phase 4/5 merge) ────────────────────────

  enterpriseSearch: (token: string, query: string, docTypes?: string[], limit = 20) =>
    request<{
      results: { id: string; type: string; title: string; text: string; score: number; metadata: Record<string, unknown> }[];
      total: number;
    }>("/api/ai/search", { method: "POST", body: JSON.stringify({ query, doc_types: docTypes, limit }) }, token),

  // ── Meeting Export (apps/api, Phase 4/5 merge) ───────────────────────────

  exportMeeting: (token: string, meetingId: string, format: "json" | "txt" | "markdown" | "html") =>
    request<Record<string, unknown>>(`/api/ai/meetings/${meetingId}/export/${format}`, {}, token),
};
