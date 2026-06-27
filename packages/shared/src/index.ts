export type MeetingMode = "meeting" | "interview" | "sales" | "presentation";
export type AgentEvent = { meetingId: string; questionDetected: boolean; suggestedResponse?: string; followUps: string[]; actionItems: string[]; sentiment: "negative" | "neutral" | "positive" | "cautious" };
