import React, { useState, useRef, useEffect, useCallback, Component } from "react";
import { useLocation } from "react-router-dom";
import ProfileCard from "../components/ProfileCard";
import PathwayCard from "../components/PathwayCard";
import WhyDrawer from "../components/WhyDrawer";
import WhatIfBar from "../components/WhatIfBar";
import DiffBanner from "../components/DiffBanner";

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "1rem", backgroundColor: "#fef2f2", color: "#991b1b", border: "1px solid #fecaca", borderRadius: "8px", margin: "1rem 0" }}>
          <strong>Error rendering section:</strong> {this.state.error?.message || "Unexpected UI error"}
        </div>
      );
    }
    return this.props.children;
  }
}

export default function Live() {
  const location = useLocation();

  // Session / connection state
  const [status, setStatus] = useState("disconnected");
  const [errorState, setErrorState] = useState(null); // { code, message, fallback }
  const [sessionId, setSessionId] = useState(null);
  const [isMuted, setIsMuted] = useState(false);

  // Profile state (driven by profile_update events from backend)
  const [profile, setProfile] = useState({});
  const [confidence, setConfidence] = useState({});
  const [confirmed, setConfirmed] = useState(false);

  // Pathways & What-If state (Phase 5)
  const [pathways, setPathways] = useState([]);
  const [excludedPathways, setExcludedPathways] = useState([]);
  const [diff, setDiff] = useState(null);
  const [constraints, setConstraints] = useState({});
  const [selectedWhyPathway, setSelectedWhyPathway] = useState(null);
  const [isUnconfirmedPreview, setIsUnconfirmedPreview] = useState(false);

  // Conversation UI
  const [transcripts, setTranscripts] = useState([]);
  const [toolCalls, setToolCalls] = useState([]);
  const [typedMessage, setTypedMessage] = useState("");

  // Refs
  const wsRef = useRef(null);
  const captureContextRef = useRef(null);
  const playbackContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const workletNodeRef = useRef(null);
  const nextPlayTimeRef = useRef(0);
  const activeSourcesRef = useRef([]);
  const transcriptEndRef = useRef(null);
  const isMutedRef = useRef(false);

  // Auto-scroll transcript to bottom
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);

  useEffect(() => {
    return () => { stopSession(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Audio helpers ──────────────────────────────────────────────────────────

  const stopAudio = () => {
    activeSourcesRef.current.forEach((src) => {
      try { src.stop(); } catch (_) {}
    });
    activeSourcesRef.current = [];
    if (playbackContextRef.current) {
      nextPlayTimeRef.current = playbackContextRef.current.currentTime;
    }
  };

  const toggleMute = () => {
    if (!isConnected) return;
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    isMutedRef.current = nextMuted;
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getAudioTracks().forEach((track) => {
        track.enabled = !nextMuted;
      });
    }
  };

  // ── Transcript helpers ─────────────────────────────────────────────────────

  const mergeTranscriptTurn = (role, newText, isFinal) => {
    const timeStr = new Date().toLocaleTimeString();
    setTranscripts((prev) => {
      if (prev.length === 0) {
        return [{ id: Math.random().toString(36).slice(2, 9), role, text: newText.trim(), final: isFinal, time: timeStr }];
      }
      const last = prev[prev.length - 1];
      if (last.role === role && !last.final) {
        const mergedText = newText.startsWith(last.text)
          ? newText
          : `${last.text} ${newText}`.trim();
        const updated = [...prev];
        updated[updated.length - 1] = { ...last, text: mergedText, final: isFinal };
        return updated;
      }
      return [...prev, { id: Math.random().toString(36).slice(2, 9), role, text: newText.trim(), final: isFinal, time: timeStr }];
    });
  };

  const finalizeLatestTurn = () => {
    setTranscripts((prev) => {
      if (prev.length === 0) return prev;
      const updated = [...prev];
      updated[updated.length - 1] = { ...updated[updated.length - 1], final: true };
      return updated;
    });
  };

  // ── Profile patch callback (from ProfileCard inline edit) ─────────────────

  const handleProfilePatch = useCallback((field, newValue) => {
    setProfile((prev) => ({ ...prev, [field]: newValue }));
    setConfidence((prev) => ({ ...prev, [field]: "stated" }));
  }, []);

  // ── What-If constraint handlers ───────────────────────────────────────────

  const handleConstraintChange = async (newConstraints) => {
    setConstraints(newConstraints);
    try {
      const res = await fetch("/api/recompute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile: profile || {},
          previous_pathway_ids: pathways.map((p) => p.id),
          constraints: newConstraints,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setPathways(data.pathways || []);
        setExcludedPathways(data.excluded || []);
        setDiff(data.diff || null);
      }
    } catch (err) {
      console.error("Recompute error:", err);
    }
  };

  const handleResetConstraints = async () => {
    handleConstraintChange({});
  };

  // ── Start session ──────────────────────────────────────────────────────────

  const startSession = async () => {
    setErrorState(null);
    setStatus("connecting");
    setIsMuted(false);
    isMutedRef.current = false;

    // Only clear profile and pathways if starting afresh without an existing session id
    if (!sessionId) {
      setProfile({});
      setConfidence({});
      setConfirmed(false);
      setPathways([]);
      setExcludedPathways([]);
      setDiff(null);
      setConstraints({});
      setSelectedWhyPathway(null);
      setIsUnconfirmedPreview(false);
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      const captureCtx = new (window.AudioContext || window.webkitAudioContext)();
      captureContextRef.current = captureCtx;
      await captureCtx.audioWorklet.addModule("/pcm-worklet-processor.js");

      const sourceNode = captureCtx.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(captureCtx, "pcm16-downsampler");
      workletNodeRef.current = workletNode;
      sourceNode.connect(workletNode);

      const playbackCtx = new (window.AudioContext || window.webkitAudioContext)();
      playbackContextRef.current = playbackCtx;
      nextPlayTimeRef.current = playbackCtx.currentTime;

      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = sessionId
        ? `${wsProtocol}//${window.location.host}/ws/live?session_id=${sessionId}`
        : `${wsProtocol}//${window.location.host}/ws/live`;
      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      workletNode.port.onmessage = (event) => {
        if (ws.readyState === WebSocket.OPEN && !isMutedRef.current) {
          ws.send(event.data);
        }
      };

      ws.onopen = () => {
        const languageHint = location.state?.languageHint || "te";
        ws.send(JSON.stringify({
          type: "start",
          language_hint: languageHint,
          session_id: sessionId,
        }));
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          setErrorState(null);
          handleIncomingAudio(event.data);
          return;
        }
        try {
          const data = JSON.parse(event.data);
          switch (data.type) {
            case "session_id":
              setSessionId(data.value);
              break;
            case "state":
              setStatus(data.value);
              break;
            case "interrupted":
              stopAudio();
              setStatus("listening");
              break;
            case "transcript":
              if (data.role === "assistant") {
                setErrorState(null);
              }
              mergeTranscriptTurn(data.role, data.text, Boolean(data.final));
              break;
            case "turn_complete":
              setErrorState(null);
              finalizeLatestTurn();
              setStatus("listening");
              break;
            case "tool_call":
              setToolCalls((prev) => [
                ...prev,
                {
                  id: data.id || Math.random().toString(36).slice(2, 9),
                  name: data.name,
                  args: data.args,
                  time: new Date().toLocaleTimeString(),
                },
              ]);
              break;
            case "profile_update":
              setProfile(data.profile || {});
              setConfidence(data.confidence || {});
              setConfirmed(data.confirmed || false);
              break;
            case "pathways":
              setPathways(data.pathways || []);
              setExcludedPathways(data.excluded || []);
              setIsUnconfirmedPreview(Boolean(data.unconfirmed));
              break;
            case "diff":
              setDiff(data.diff || null);
              if (data.pathways) setPathways(data.pathways);
              if (data.excluded) setExcludedPathways(data.excluded);
              break;
            case "error":
              setErrorState({
                code: data.code || "unknown_error",
                message: data.message || "An unexpected error occurred.",
                fallback: data.fallback || "retry",
              });
              setStatus("error");
              break;
            default:
              break;
          }
        } catch (err) {
          console.error("WS parse error:", err);
        }
      };

      ws.onerror = () => {
        setErrorState({
          code: "connection_lost",
          message: "WebSocket error. Is the backend running on port 8000?",
          fallback: "retry",
        });
        setStatus("error");
      };

      ws.onclose = () => {
        setStatus((s) => (s === "error" ? s : "disconnected"));
      };
    } catch (err) {
      setErrorState({
        code: "media_error",
        message: err.message || "Failed to initialize microphone or connection",
        fallback: "retry",
      });
      setStatus("error");
      stopSession();
    }
  };


  // ── Playback ───────────────────────────────────────────────────────────────

  const handleIncomingAudio = (arrayBuffer) => {
    const playbackCtx = playbackContextRef.current;
    if (!playbackCtx) return;
    const pcm16 = new Int16Array(arrayBuffer);
    if (pcm16.length === 0) return;
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) float32[i] = pcm16[i] / 32768.0;
    const audioBuffer = playbackCtx.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);
    const source = playbackCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playbackCtx.destination);
    const ct = playbackCtx.currentTime;
    if (nextPlayTimeRef.current < ct) nextPlayTimeRef.current = ct + 0.05;
    source.start(nextPlayTimeRef.current);
    nextPlayTimeRef.current += audioBuffer.duration;
    activeSourcesRef.current.push(source);
    source.onended = () => {
      activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== source);
    };
  };

  // ── Stop session ───────────────────────────────────────────────────────────

  const stopSession = () => {
    stopAudio();
    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
    captureContextRef.current?.close().catch(() => {});
    captureContextRef.current = null;
    playbackContextRef.current?.close().catch(() => {});
    playbackContextRef.current = null;
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN)
        wsRef.current.send(JSON.stringify({ type: "stop" }));
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus("disconnected");
    setIsMuted(false);
    isMutedRef.current = false;
  };

  const handleRetry = () => {
    stopSession();
    setTimeout(() => {
      startSession();
    }, 100);
  };

  const handleUseTypedInput = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      startSession();
    } else {
      setStatus("listening");
    }
    setTimeout(() => {
      document.getElementById("typed-input")?.focus();
    }, 150);
  };

  // ── Typed input ────────────────────────────────────────────────────────────

  const sendTextTurn = () => {
    if (!typedMessage.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    const msg = typedMessage.trim();
    wsRef.current.send(JSON.stringify({ type: "text", text: msg }));
    mergeTranscriptTurn("user", msg, true);
    setTypedMessage("");
  };

  const isConnected = status !== "disconnected" && status !== "error";

  const statusColor = isMuted
    ? "#f59e0b"
    : {
        listening:    "#10b981",
        speaking:     "#3b82f6",
        thinking:     "#8b5cf6",
        connecting:   "#f59e0b",
        reconnecting: "#ea580c",
        error:        "#ef4444",
      }[status] || "#94a3b8";

  const statusLabel = isMuted
    ? "Microphone Muted"
    : {
        listening:    "Listening…",
        speaking:     "Assistant speaking",
        thinking:     "Processing…",
        connecting:   "Connecting to Gemini Live…",
        reconnecting: "Reconnecting session…",
        error:        "Connection Error",
      }[status] || "Ready to Connect";

  const micIcon = isMuted
    ? "🔇"
    : {
        speaking:     "🔊",
        thinking:     "⚙️",
        reconnecting: "🔄",
        error:        "⚠️",
      }[status] || "🎙️";

  return (
    <div style={{ maxWidth: 960, margin: "1.5rem auto", padding: "0 1rem", fontFamily: "var(--sans, sans-serif)" }}>

      {/* Two-column layout on wide screens: Voice+Transcript | ProfileCard */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "1.5rem" }}>

        {/* ── Left column ── */}
        <div>
          {/* Voice Panel */}
          <div style={{
            border: "1px solid #e2e8f0", borderRadius: "12px", padding: "1.75rem",
            backgroundColor: "#ffffff", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)",
            marginBottom: "1.25rem", textAlign: "center",
          }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.9rem" }}>
              {/* Large mic indicator / click to toggle mute when connected */}
              <button
                type="button"
                onClick={isConnected ? toggleMute : startSession}
                title={isConnected ? (isMuted ? "Click to unmute" : "Click to mute") : "Click to start"}
                style={{
                  width: 96, height: 96, borderRadius: "50%",
                  backgroundColor: `${statusColor}20`,
                  border: `4px solid ${statusColor}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  transition: "all 0.3s ease",
                  boxShadow: isConnected ? `0 0 22px ${statusColor}40` : "none",
                  cursor: "pointer", padding: 0,
                }}
              >
                <span style={{ fontSize: "2.4rem" }}>{micIcon}</span>
              </button>

              <div>
                <h3 style={{ margin: "0.2rem 0", color: "#0f172a", fontSize: "1.25rem" }}>
                  {statusLabel}
                </h3>
                <p style={{ margin: 0, color: "#64748b", fontSize: "0.85rem" }}>
                  Telugu &bull; Hindi &bull; English &bull; Natural code-switching
                </p>
              </div>

              <div style={{ display: "flex", gap: "0.75rem" }}>
                {!isConnected ? (
                  <button
                    id="btn-start-voice"
                    onClick={startSession}
                    style={{
                      padding: "0.7rem 1.6rem", fontSize: "1rem", fontWeight: "bold",
                      cursor: "pointer", borderRadius: "8px", border: "none",
                      backgroundColor: "#2563eb", color: "#fff",
                      boxShadow: "0 2px 4px rgba(37,99,235,0.25)",
                    }}
                  >
                    🎙️ Start Live Voice
                  </button>
                ) : (
                  <>
                    <button
                      id="btn-toggle-mic"
                      onClick={toggleMute}
                      style={{
                        padding: "0.7rem 1.4rem", fontSize: "1rem", fontWeight: "bold",
                        cursor: "pointer", borderRadius: "8px", border: "1px solid #cbd5e1",
                        backgroundColor: isMuted ? "#fef3c7" : "#f1f5f9",
                        color: isMuted ? "#b45309" : "#1e293b",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                      }}
                    >
                      {isMuted ? "🎙️ Unmute Mic" : "🔇 Mute Mic"}
                    </button>
                    <button
                      id="btn-disconnect"
                      onClick={stopSession}
                      style={{
                        padding: "0.7rem 1.2rem", fontSize: "0.95rem", fontWeight: "bold",
                        cursor: "pointer", borderRadius: "8px", border: "none",
                        backgroundColor: "#dc2626", color: "#fff",
                        boxShadow: "0 2px 4px rgba(220,38,38,0.2)",
                      }}
                    >
                      ⏹️ Disconnect
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Error banner */}
          {errorState && (
            <div
              id="live-error-banner"
              style={{
                padding: "1rem 1.25rem",
                marginBottom: "1.25rem",
                backgroundColor: "#fef2f2",
                color: "#991b1b",
                border: "1px solid #fecaca",
                borderRadius: "8px",
                boxShadow: "0 2px 4px rgba(239,68,68,0.08)",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
                <div>
                  <div style={{ fontWeight: "bold", fontSize: "0.95rem", marginBottom: "0.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span>⚠️</span>
                    <span>{errorState.code ? `Error (${errorState.code})` : "Error"}</span>
                  </div>
                  <p style={{ margin: 0, fontSize: "0.9rem", color: "#7f1d1d", lineHeight: 1.4 }}>
                    {errorState.message}
                  </p>
                </div>
                <div style={{ display: "flex", gap: "0.6rem", alignItems: "center", marginTop: "0.25rem" }}>
                  <button
                    id="btn-error-retry"
                    type="button"
                    onClick={handleRetry}
                    style={{
                      padding: "0.45rem 0.9rem",
                      fontSize: "0.85rem",
                      fontWeight: "bold",
                      cursor: "pointer",
                      borderRadius: "6px",
                      border: "1px solid #dc2626",
                      backgroundColor: "#dc2626",
                      color: "#ffffff",
                      boxShadow: "0 1px 2px rgba(220,38,38,0.2)",
                    }}
                  >
                    🔄 Retry
                  </button>
                  <button
                    id="btn-error-typed"
                    type="button"
                    onClick={handleUseTypedInput}
                    style={{
                      padding: "0.45rem 0.9rem",
                      fontSize: "0.85rem",
                      fontWeight: "bold",
                      cursor: "pointer",
                      borderRadius: "6px",
                      border: "1px solid #cbd5e1",
                      backgroundColor: "#ffffff",
                      color: "#1e293b",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                    }}
                  >
                    ⌨️ Use typed input
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Tool call activity (visible only when ping is called) */}
          {toolCalls.length > 0 && (
            <div style={{
              border: "1px solid #e2e8f0", borderRadius: "8px",
              padding: "0.9rem", marginBottom: "1.25rem",
              backgroundColor: "#f8fafc",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h4 style={{ margin: 0, color: "#1e293b", fontSize: "0.9rem" }}>Tool Activity</h4>
                <span style={{ fontSize: "0.75rem", color: "#64748b" }}>{toolCalls.length} call(s)</span>
              </div>
              <ul style={{ margin: "0.4rem 0 0 0", paddingLeft: "1rem" }}>
                {toolCalls.map((tc) => (
                  <li key={tc.id} style={{ margin: "0.2rem 0", fontSize: "0.85rem" }}>
                    <strong>[{tc.time}] {tc.name}</strong> &rarr; <span style={{ color: "#16a34a" }}>PONG</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Transcript */}
          <div style={{
            border: "1px solid #e2e8f0", borderRadius: "8px",
            padding: "1.1rem", marginBottom: "1.25rem",
            backgroundColor: "#ffffff", boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
              <h3 style={{ margin: 0, fontSize: "0.95rem", color: "#0f172a" }}>Live Transcript</h3>
              <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>One line per turn</span>
            </div>
            <div style={{
              minHeight: 200, maxHeight: 340, overflowY: "auto",
              backgroundColor: "#f8fafc", border: "1px solid #e2e8f0",
              padding: "0.75rem", borderRadius: "6px",
              display: "flex", flexDirection: "column", gap: "0.6rem",
            }}>
              {transcripts.length === 0 ? (
                <p style={{ color: "#94a3b8", fontStyle: "italic", margin: "auto", fontSize: "0.85rem" }}>
                  Conversation will appear here turn-by-turn.
                </p>
              ) : (
                transcripts.map((t) => (
                  <div key={t.id} style={{ display: "flex", flexDirection: "column", alignItems: t.role === "user" ? "flex-end" : "flex-start" }}>
                    <div style={{
                      maxWidth: "85%", padding: "0.5rem 0.8rem", borderRadius: "8px",
                      backgroundColor: t.role === "user" ? "#dbeafe" : "#f1f5f9",
                      color: t.role === "user" ? "#1e40af" : "#0f172a",
                      border: t.role === "user" ? "1px solid #bfdbfe" : "1px solid #e2e8f0",
                      fontSize: "0.9rem", lineHeight: 1.45,
                    }}>
                      <div style={{ fontSize: "0.7rem", color: "#64748b", marginBottom: "0.15rem" }}>
                        <strong>{t.role === "user" ? "You" : "Assistant"}</strong> &bull; {t.time}
                      </div>
                      {t.text}
                    </div>
                  </div>
                ))
              )}
              <div ref={transcriptEndRef} />
            </div>
          </div>

          {/* Typed input */}
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input
              type="text"
              id="typed-input"
              value={typedMessage}
              placeholder="Type in Telugu, Hindi, or English… (e.g. నేను 10వ తరగతి చదివాను)"
              onChange={(e) => setTypedMessage(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendTextTurn()}
              disabled={!isConnected}
              style={{
                flex: 1, padding: "0.55rem 0.85rem", fontSize: "0.92rem",
                borderRadius: "6px", border: "1px solid #cbd5e1",
                fontFamily: "var(--sans, sans-serif)",
              }}
            />
            <button
              id="btn-send-text"
              onClick={sendTextTurn}
              disabled={!isConnected || !typedMessage.trim()}
              style={{
                padding: "0.55rem 1.1rem", fontWeight: "bold",
                cursor: isConnected && typedMessage.trim() ? "pointer" : "not-allowed",
                borderRadius: "6px", border: "none",
                backgroundColor: isConnected && typedMessage.trim() ? "#2563eb" : "#cbd5e1",
                color: "#fff",
              }}
            >
              Send
            </button>
          </div>
        </div>

        {/* ── Right column: ProfileCard ── */}
        <div>
          <ProfileCard
            profile={profile}
            confidence={confidence}
            confirmed={confirmed}
            sessionId={sessionId}
            onPatch={handleProfilePatch}
          />

          {/* Session info (dev aid) */}
          {sessionId && (
            <div style={{
              padding: "0.5rem 0.75rem", borderRadius: "6px",
              backgroundColor: "#f8fafc", border: "1px solid #e2e8f0",
              fontSize: "0.72rem", color: "#64748b",
            }}>
              Session: <code style={{ fontSize: "0.7rem" }}>{sessionId.slice(0, 8)}…</code>
            </div>
          )}
        </div>
      </div>

      {/* ── Pathways and What-If Section (Phase 5) ── */}
      <ErrorBoundary>
        {(pathways.length > 0 || diff || Object.keys(constraints).length > 0) && (
          <div style={{ marginTop: "2rem", borderTop: "1px solid #e2e8f0", paddingTop: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
              <div>
                <h2 style={{ fontSize: "1.3rem", fontWeight: "bold", color: "#0f172a", margin: 0 }}>
                  Recommended Livelihood Pathways
                </h2>
                <p style={{ fontSize: "0.85rem", color: "#64748b", margin: "0.25rem 0 0 0" }}>
                  Tailored based on your stated background, constraints, and verified local opportunities.
                </p>
              </div>
              {isUnconfirmedPreview && (
                <span style={{
                  fontSize: "0.75rem", backgroundColor: "#fef3c7", color: "#92400e",
                  border: "1px solid #fcd34d", padding: "0.25rem 0.6rem", borderRadius: "9999px",
                  fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "0.25rem"
                }}>
                  <span>⚠️</span> Unconfirmed Profile Preview
                </span>
              )}
            </div>

            {/* What-If Simulation Bar */}
            <WhatIfBar
              constraints={constraints}
              onConstraintChange={handleConstraintChange}
              onReset={handleResetConstraints}
            />

            {/* Diff Banner */}
            <DiffBanner diff={diff} excluded={excludedPathways} />

            {/* Pathway Cards Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1rem" }}>
              {pathways.map((pw) => (
                <PathwayCard
                  key={pw.id}
                  pathway={pw}
                  onSelectWhy={(p) => setSelectedWhyPathway(p)}
                />
              ))}
            </div>
          </div>
        )}

        {/* WhyDrawer */}
        {selectedWhyPathway && (
          <WhyDrawer
            pathway={selectedWhyPathway}
            profile={profile}
            onClose={() => setSelectedWhyPathway(null)}
          />
        )}
      </ErrorBoundary>
    </div>
  );
}
