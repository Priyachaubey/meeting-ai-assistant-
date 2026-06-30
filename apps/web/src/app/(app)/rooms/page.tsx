"use client";
import { MeetingRoom } from "@/components/meeting-room";

// Phase 4/5 merge: the new real-time multi-participant meeting room (own video/audio
// signalling via apps/meeting-server), kept on its own route deliberately. The upstream
// version of this file replaced /live/page.tsx outright — which would have swapped out
// the existing single-user system-audio-capture copilot (LiveMeeting, the product's
// original core feature) for this instead. That's exactly the kind of "remove an existing
// page" the merge was supposed to avoid, so /live is untouched and this lives at /rooms.

export default function RoomsPage() {
  return <MeetingRoom />;
}
