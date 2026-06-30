import { create } from "zustand";
export type TranscriptLine = { id: string; speaker: string; text: string; timestamp: string; kind?: "question" | "statement" };
type MeetingState = { active: boolean; muted: boolean; lines: TranscriptLine[]; start: () => void; stop: () => void; toggleMute: () => void; addLine: (line: TranscriptLine) => void };
export const useMeetingStore = create<MeetingState>((set) => ({ active: false, muted: false, lines: [], start: () => set({ active: true }), stop: () => set({ active: false }), toggleMute: () => set((s) => ({ muted: !s.muted })), addLine: (line) => set((s) => ({ lines: [...s.lines, line] })) }));
