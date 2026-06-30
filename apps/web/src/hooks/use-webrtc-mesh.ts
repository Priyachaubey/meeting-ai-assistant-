"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Real WebRTC mesh client for the meeting room.
 *
 * The backend half of this (apps/meeting-server/app/signalling/manager.py — offer/answer/
 * ICE-candidate routing between specific participants) already existed before this file was
 * written; it was real, correct, and unused. This hook is the browser-side half: capture
 * real camera/mic via getUserMedia, open one RTCPeerConnection per remote participant, and
 * exchange SDP/ICE through the room's existing WebSocket using the `signalling` message type
 * the backend already routes (SignallingMessage.offer/answer/ice_candidate in meeting-server).
 *
 * Mesh topology (every participant connects directly to every other participant) — the
 * simplest correct topology and fine for small meetings (roughly up to 6-8 people; beyond
 * that each browser is opening N-1 simultaneous encode/decode pipelines, which is a real
 * scaling wall mesh topology hits everywhere, not specific to this implementation — an SFU
 * is the standard fix, and a real architecture change, not something to silently swap in
 * here).
 *
 * STUN: uses Google's public STUN servers (no API key — these are free, unauthenticated,
 * publicly operated for exactly this purpose, not a paid/new provider).
 * TURN: NEXT_PUBLIC_TURN_URL / _USERNAME / _CREDENTIAL, all optional. Without a TURN server,
 * any two participants both behind symmetric NAT or restrictive corporate firewalls will
 * fail to connect to each other — STUN alone can't solve that, full stop, no code fixes it.
 * This is real infrastructure (e.g. self-hosted coturn, or a managed TURN provider) that has
 * to actually be deployed and tested; this hook is wired to use one the moment it's
 * configured, but cannot stand one up from here.
 *
 * IMPORTANT — what this can't verify from this sandbox: there's no second browser here to
 * actually open two tabs and confirm a real peer connection completes ICE negotiation and
 * media flows. The signaling message shapes match the backend's `SignallingMessage` exactly
 * (verified by reading meeting-server's signalling/manager.py directly), and the SDP/ICE
 * handling follows the standard WebRTC perfect-negotiation pattern — but "the offer/answer
 * exchange is correctly shaped" and "two real browsers behind real NATs successfully
 * establish a connection" are different claims. The second one needs real testing this
 * environment cannot do.
 */

export interface RemotePeer {
  participantId: string;
  stream: MediaStream | null;
  connectionState: RTCPeerConnectionState;
}

interface SignallingEnvelope {
  type: "offer" | "answer" | "ice_candidate";
  sender_id: string;
  target_id: string;
  sdp?: RTCSessionDescriptionInit;
  candidate?: RTCIceCandidateInit;
}

function buildIceServers(): RTCIceServer[] {
  const servers: RTCIceServer[] = [
    { urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] },
  ];
  const turnUrl = process.env.NEXT_PUBLIC_TURN_URL;
  if (turnUrl) {
    servers.push({
      urls: turnUrl,
      username: process.env.NEXT_PUBLIC_TURN_USERNAME,
      credential: process.env.NEXT_PUBLIC_TURN_CREDENTIAL,
    });
  }
  return servers;
}

export function useWebRTCMesh(opts: {
  myConnectionId: string | null;
  sendSignalling: (envelope: { type: string; data: Record<string, unknown> }) => void;
  isMuted: boolean;
  isVideoOn: boolean;
}) {
  const { myConnectionId, sendSignalling, isMuted, isVideoOn } = opts;

  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [remotePeers, setRemotePeers] = useState<Record<string, RemotePeer>>({});

  const localStreamRef = useRef<MediaStream | null>(null);
  const peersRef = useRef<Record<string, RTCPeerConnection>>({});
  // Buffers ICE candidates that arrive before the remote description is set — a normal race
  // in real signaling, not an edge case; dropping these silently is the #1 cause of WebRTC
  // connections that "work most of the time" and mysteriously fail the rest.
  const pendingCandidatesRef = useRef<Record<string, RTCIceCandidateInit[]>>({});

  // ── 1. Capture real camera + mic ────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    let stream: MediaStream | null = null;

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setMediaError("This browser doesn't support camera/microphone capture.");
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        localStreamRef.current = stream;
        setLocalStream(stream);
      } catch (err) {
        // Permission denied, no device present, device in use by another app — these are
        // real, common, user-facing outcomes, not exceptional ones. Surface a real message
        // instead of a generic console error the user never sees.
        const message =
          err instanceof DOMException && err.name === "NotAllowedError"
            ? "Camera/microphone access was denied. Allow access in your browser's site settings and rejoin."
            : err instanceof DOMException && err.name === "NotFoundError"
              ? "No camera or microphone was found on this device."
              : `Could not access camera/microphone: ${err instanceof Error ? err.message : String(err)}`;
        setMediaError(message);
      }
    }
    start();

    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
      localStreamRef.current = null;
    };
  }, []);

  // Reflect mute/camera-off toggles onto the real tracks — not just UI state. This is the
  // other half of the existing isMuted/isVideoOn buttons: previously they only flipped a
  // boolean with no real track behind them to disable.
  useEffect(() => {
    localStreamRef.current?.getAudioTracks().forEach((t) => { t.enabled = !isMuted; });
  }, [isMuted]);
  useEffect(() => {
    localStreamRef.current?.getVideoTracks().forEach((t) => { t.enabled = isVideoOn; });
  }, [isVideoOn]);

  // ── 2. Peer connection lifecycle ────────────────────────────────────────

  const closePeer = useCallback((peerId: string) => {
    peersRef.current[peerId]?.close();
    delete peersRef.current[peerId];
    delete pendingCandidatesRef.current[peerId];
    setRemotePeers((prev) => {
      const next = { ...prev };
      delete next[peerId];
      return next;
    });
  }, []);

  const createPeerConnection = useCallback(
    (peerId: string): RTCPeerConnection => {
      const pc = new RTCPeerConnection({ iceServers: buildIceServers() });

      localStreamRef.current?.getTracks().forEach((track) => {
        pc.addTrack(track, localStreamRef.current!);
      });

      pc.onicecandidate = (event) => {
        if (!event.candidate || !myConnectionId) return;
        sendSignalling({
          type: "signalling",
          data: {
            type: "ice_candidate",
            sender_id: myConnectionId,
            target_id: peerId,
            candidate: event.candidate.toJSON(),
          },
        });
      };

      pc.ontrack = (event) => {
        const [stream] = event.streams;
        setRemotePeers((prev) => ({
          ...prev,
          [peerId]: { participantId: peerId, stream: stream ?? null, connectionState: pc.connectionState },
        }));
      };

      pc.onconnectionstatechange = () => {
        setRemotePeers((prev) =>
          prev[peerId] ? { ...prev, [peerId]: { ...prev[peerId], connectionState: pc.connectionState } } : prev
        );
        if (pc.connectionState === "failed" || pc.connectionState === "closed") {
          // A "failed" state here almost always means ICE couldn't find a viable path — see
          // this file's top comment on TURN. Closing rather than silently leaving a dead
          // connection object around avoids a slow memory/socket leak across a long meeting
          // with several reconnect attempts.
          closePeer(peerId);
        }
      };

      peersRef.current[peerId] = pc;
      return pc;
    },
    [myConnectionId, sendSignalling, closePeer]
  );

  /** Call when a new participant_joined event arrives. Tie-broken by connection ID so only
   * one side initiates the offer — both sides racing to offer simultaneously (glare) is a
   * real, well-known WebRTC bug class; this avoids it entirely rather than implementing full
   * perfect-negotiation rollback logic for a case that's simple to just not have happen. */
  const connectToPeer = useCallback(
    async (peerId: string) => {
      if (!myConnectionId || peerId === myConnectionId || peersRef.current[peerId]) return;
      if (myConnectionId >= peerId) return; // the other side will initiate instead

      const pc = createPeerConnection(peerId);
      try {
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        sendSignalling({
          type: "signalling",
          data: { type: "offer", sender_id: myConnectionId, target_id: peerId, sdp: offer },
        });
      } catch (err) {
        console.error("Failed to create WebRTC offer for", peerId, err);
        closePeer(peerId);
      }
    },
    [myConnectionId, createPeerConnection, sendSignalling, closePeer]
  );

  /** Feed every `signalling`-type WS message here (offer / answer / ice_candidate), already
   * routed to us specifically by the backend's SignallingManager. */
  const handleSignallingMessage = useCallback(
    async (envelope: SignallingEnvelope) => {
      const { type, sender_id: peerId } = envelope;

      if (type === "offer") {
        const pc = peersRef.current[peerId] ?? createPeerConnection(peerId);
        try {
          await pc.setRemoteDescription(new RTCSessionDescription(envelope.sdp!));
          const queued = pendingCandidatesRef.current[peerId] || [];
          for (const c of queued) await pc.addIceCandidate(new RTCIceCandidate(c));
          pendingCandidatesRef.current[peerId] = [];

          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          if (myConnectionId) {
            sendSignalling({
              type: "signalling",
              data: { type: "answer", sender_id: myConnectionId, target_id: peerId, sdp: answer },
            });
          }
        } catch (err) {
          console.error("Failed to handle WebRTC offer from", peerId, err);
        }
      } else if (type === "answer") {
        const pc = peersRef.current[peerId];
        if (!pc) return;
        try {
          await pc.setRemoteDescription(new RTCSessionDescription(envelope.sdp!));
          const queued = pendingCandidatesRef.current[peerId] || [];
          for (const c of queued) await pc.addIceCandidate(new RTCIceCandidate(c));
          pendingCandidatesRef.current[peerId] = [];
        } catch (err) {
          console.error("Failed to handle WebRTC answer from", peerId, err);
        }
      } else if (type === "ice_candidate") {
        const pc = peersRef.current[peerId];
        const candidate = envelope.candidate;
        if (!candidate) return;
        if (pc && pc.remoteDescription) {
          try {
            await pc.addIceCandidate(new RTCIceCandidate(candidate));
          } catch (err) {
            console.error("Failed to add ICE candidate from", peerId, err);
          }
        } else {
          // Remote description not set yet — buffer it (see top-of-file note).
          pendingCandidatesRef.current[peerId] = [...(pendingCandidatesRef.current[peerId] || []), candidate];
        }
      }
    },
    [createPeerConnection, myConnectionId, sendSignalling]
  );

  // ── 3. Screen sharing ────────────────────────────────────────────────────
  // Swaps the outgoing video track on every active peer connection via replaceTrack — the
  // standard WebRTC pattern for this, and notably does NOT renegotiate the connection (no
  // new offer/answer needed), since the track's m-line slot in the SDP doesn't change, only
  // its content. Reverts to the camera track automatically if the user stops sharing via the
  // browser's own "Stop sharing" UI (the stream's inactive `ended` event), not just via this
  // component's button — that's a real, common way people stop screen share and needs to be
  // handled the same as clicking the button here, or the UI would silently get stuck showing
  // a dead screen-share tile.
  const screenStreamRef = useRef<MediaStream | null>(null);
  const [isScreenSharing, setIsScreenSharing] = useState(false);

  const stopScreenShare = useCallback(async () => {
    const cameraTrack = localStreamRef.current?.getVideoTracks()[0] ?? null;
    for (const pc of Object.values(peersRef.current)) {
      const sender = pc.getSenders().find((s) => s.track?.kind === "video");
      if (sender) await sender.replaceTrack(cameraTrack);
    }
    screenStreamRef.current?.getTracks().forEach((t) => t.stop());
    screenStreamRef.current = null;
    setIsScreenSharing(false);
  }, []);

  const startScreenShare = useCallback(async () => {
    if (!navigator.mediaDevices?.getDisplayMedia) {
      setMediaError("This browser doesn't support screen sharing.");
      return;
    }
    try {
      const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      const screenTrack = screenStream.getVideoTracks()[0];
      screenStreamRef.current = screenStream;

      for (const pc of Object.values(peersRef.current)) {
        const sender = pc.getSenders().find((s) => s.track?.kind === "video");
        if (sender) await sender.replaceTrack(screenTrack);
      }

      // The browser's native "Stop sharing" button/bar ends the track directly — this is the
      // only reliable way to detect that and fall back to the camera automatically.
      screenTrack.addEventListener("ended", () => { stopScreenShare(); });

      setIsScreenSharing(true);
    } catch (err) {
      // The user clicking "Cancel" on the share picker also throws NotAllowedError — that's
      // not a real error worth surfacing, it's a normal cancellation.
      if (err instanceof DOMException && err.name === "NotAllowedError") return;
      setMediaError(`Could not start screen sharing: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [stopScreenShare]);

  const toggleScreenShare = useCallback(() => {
    if (isScreenSharing) stopScreenShare();
    else startScreenShare();
  }, [isScreenSharing, startScreenShare, stopScreenShare]);

  // Close every peer connection on unmount — meetings end, components do too.
  useEffect(() => {
    return () => {
      Object.keys(peersRef.current).forEach(closePeer);
    };
  }, [closePeer]);

  // ── 4. Local recording ───────────────────────────────────────────────────
  // "Local" deliberately: this records only what's actually available in THIS browser tab —
  // your own camera/mic, composited with remote participants' audio (via Web Audio, so a
  // recording isn't just your own voice). It does NOT record other participants' video —
  // doing that for real means compositing multiple live video streams onto a canvas in real
  // time, which is a meaningfully heavier, separately-scoped feature, not a natural
  // extension of "press record." This produces a real, complete, downloadable recording of
  // your own participation with full audio context — not a placeholder.
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordingAudioContextRef = useRef<AudioContext | null>(null);
  const [isRecording, setIsRecordingState] = useState(false);
  const [isRecordingPaused, setIsRecordingPaused] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [recordingBlobUrl, setRecordingBlobUrlState] = useState<string | null>(null);
  // Mirrors recordingBlobUrl via a ref so the unmount-cleanup effect below (empty deps, by
  // design — it should only run once, on actual unmount) can always revoke the *current*
  // URL rather than a stale closure over whatever it was when the effect was first set up.
  const recordingBlobUrlRef = useRef<string | null>(null);
  const setRecordingBlobUrl = useCallback((updater: string | null | ((prev: string | null) => string | null)) => {
    setRecordingBlobUrlState((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      recordingBlobUrlRef.current = next;
      return next;
    });
  }, []);
  const [recordingFileExtension, setRecordingFileExtension] = useState("webm");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const recordingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
  }, []);

  const startRecording = useCallback(() => {
    if (!localStreamRef.current) {
      setRecordingError("Camera/microphone isn't ready yet — wait a moment and try again.");
      return;
    }
    if (typeof MediaRecorder === "undefined") {
      setRecordingError("This browser doesn't support recording.");
      return;
    }
    setRecordingError(null);
    setRecordingBlobUrl((prev) => {
      // A previous recording's object URL would otherwise leak — revoke it before starting
      // a fresh one rather than only ever doing this on unmount.
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });

    // Mix local mic audio with every connected remote participant's audio via Web Audio —
    // a recording of only your own voice with everyone else silent would be close to
    // useless. Video track is local-only (see this section's top comment on why).
    const audioContext = new AudioContext();
    recordingAudioContextRef.current = audioContext;
    const destination = audioContext.createMediaStreamDestination();

    const localAudioTrack = localStreamRef.current.getAudioTracks()[0];
    if (localAudioTrack) {
      audioContext.createMediaStreamSource(new MediaStream([localAudioTrack])).connect(destination);
    }
    for (const peer of Object.values(remotePeers)) {
      const remoteAudioTrack = peer.stream?.getAudioTracks()[0];
      if (remoteAudioTrack) {
        try {
          audioContext.createMediaStreamSource(new MediaStream([remoteAudioTrack])).connect(destination);
        } catch {
          // A track from a peer that's mid-disconnect can throw here — skip it rather than
          // aborting the whole recording over one participant's audio.
        }
      }
    }

    const videoTrack = localStreamRef.current.getVideoTracks()[0];
    const recordingStream = new MediaStream([
      ...(videoTrack ? [videoTrack] : []),
      ...destination.stream.getAudioTracks(),
    ]);

    // Codec fallback list, most-preferred first — Safari in particular doesn't support
    // vp9/opus in a webm container at all; without checking isTypeSupported() first,
    // `new MediaRecorder(stream, {mimeType: "video/webm;codecs=vp9"})` throws synchronously
    // on Safari instead of falling back, which would silently break recording for exactly
    // the browser this document's own validation section asks to test against.
    const mimeCandidates = [
      "video/webm;codecs=vp9,opus",
      "video/webm;codecs=vp8,opus",
      "video/webm",
      "video/mp4",
    ];
    const mimeType = mimeCandidates.find((m) => MediaRecorder.isTypeSupported(m));
    if (!mimeType) {
      setRecordingError("No supported recording format found in this browser.");
      audioContext.close();
      return;
    }
    setRecordingFileExtension(mimeType.startsWith("video/mp4") ? "mp4" : "webm");

    recordedChunksRef.current = [];
    const recorder = new MediaRecorder(recordingStream, { mimeType });
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) recordedChunksRef.current.push(event.data);
    };
    recorder.onerror = () => {
      setRecordingError("Recording failed unexpectedly — partial recording may still be available below.");
    };
    recorder.onstop = () => {
      const blob = new Blob(recordedChunksRef.current, { type: mimeType });
      setRecordingBlobUrl(URL.createObjectURL(blob));
      setIsRecordingState(false);
      setIsRecordingPaused(false);
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
      recordingAudioContextRef.current?.close();
      recordingAudioContextRef.current = null;
    };

    recorder.start(1000); // 1s timeslice — bounds how much is lost if the tab crashes mid-recording
    mediaRecorderRef.current = recorder;
    setIsRecordingState(true);
    setRecordingSeconds(0);
    recordingTimerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
  }, [remotePeers]);

  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.pause();
      setIsRecordingPaused(true);
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
    }
  }, []);

  const resumeRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "paused") {
      mediaRecorderRef.current.resume();
      setIsRecordingPaused(false);
      recordingTimerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
    }
  }, []);

  // Stop cleanly on unmount rather than leaking a MediaRecorder + AudioContext if someone
  // navigates away mid-recording. Also revokes any finished-but-undownloaded recording's
  // blob URL — found during a memory-leak audit: it was correctly revoked when starting a
  // *new* recording, but never when the component unmounted with one still sitting around
  // (e.g. the user leaves the meeting without clicking download).
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current?.state !== "inactive") mediaRecorderRef.current?.stop();
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      recordingAudioContextRef.current?.close();
      if (recordingBlobUrlRef.current) URL.revokeObjectURL(recordingBlobUrlRef.current);
    };
  }, []);

  return {
    localStream,
    mediaError,
    remotePeers,
    connectToPeer,
    disconnectFromPeer: closePeer,
    handleSignallingMessage,
    isScreenSharing,
    toggleScreenShare,
    isRecording,
    isRecordingPaused,
    recordingError,
    recordingBlobUrl,
    recordingFileExtension,
    recordingSeconds,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
  };
}
