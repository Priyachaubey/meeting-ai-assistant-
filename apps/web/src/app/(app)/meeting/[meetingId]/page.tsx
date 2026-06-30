"use client";

import { useParams } from "next/navigation";
import { MeetingRoom } from "@/components/meeting-room";

// The dedicated, shareable, refreshable meeting URL this document specifically asked for:
// /meeting/{meetingId} — previously didn't exist. /rooms always showed a create/join modal
// over a static page with no per-meeting URL at all: creating or joining a room only ever
// flipped internal React state, so the address bar stayed on /rooms regardless of which
// meeting you were in. That meant no real shareable link, no bookmarking a specific meeting,
// and refreshing the page during a live meeting dropped you back to the picker with no way
// back in except re-joining via the modal's "meeting code" field.
//
// This route fixes that properly rather than papering over it: MeetingRoom now accepts an
// optional `initialRoomId` (see its own comment) and auto-joins that room directly, skipping
// the modal entirely. Creating or joining a meeting from /rooms now also navigates here (see
// meeting-room.tsx's handleStart), so this becomes the real URL for any live meeting either
// way you got into it.

export default function MeetingByIdPage() {
  const params = useParams<{ meetingId: string }>();
  return <MeetingRoom initialRoomId={params.meetingId} />;
}
