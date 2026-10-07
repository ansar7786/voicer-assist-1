import { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";

export default function Live() {
  const location = useLocation();
  const [status, setStatus] = useState("disconnected"); // disconnected, connecting, listening, speaking, thinking, reconnecting, error
  const [errorMsg, setErrorMsg] = useState("");
  const [transcripts, setTranscripts] = useState([]);
  const [toolCalls, setToolCalls] = useState([]);
  const [typedMessage, setTypedMessage] = useState("");

  const wsRef = useRef(null);
  const captureContextRef = useRef(null);
  const playbackContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const workletNodeRef = useRef(null);
  const nextPlayTimeRef = useRef(0);
  const activeSourcesRef = useRef([]);

  useEffect(() => {
    return () => {
      stopSession();
    };
  }, []);

  const stopAudio = () => {
    activeSourcesRef.current.forEach((src) => {
      try {
        src.stop();
      } catch (e) {
        // already stopped
      }
    });
    activeSourcesRef.current = [];
    if (playbackContextRef.current) {
      nextPlayTimeRef.current = playbackContextRef.current.currentTime;
    }
  };

  const mergeTranscriptTurn = (role, newText, isFinal) => {
    const timeStr = new Date().toLocaleTimeString();
    setTranscripts((prev) => {
      if (prev.length === 0) {
        return [{ id: Math.random().toString(36).substring(2, 9), role, text: newText.trim(), final: isFinal, time: timeStr }];
      }
      const last = prev[prev.length - 1];
      if (last.role === role && !last.final) {
        const mergedText = newText.startsWith(last.text)
          ? newText
          : `${last.text} ${newText}`.trim();
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...last,
          text: mergedText,
          final: isFinal,
        };
        return updated;
      } else {
        return [...prev, { id: Math.random().toString(36).substring(2, 9), role, text: newText.trim(), final: isFinal, time: timeStr }];
      }
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

  const startSession = async () => {
    setErrorMsg("");
    setStatus("connecting");

    try {
      // 1. Microphone capture with echo cancellation
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // 2. Capture AudioContext & AudioWorklet (16 kHz downsampling)
      const captureCtx = new (window.AudioContext || window.webkitAudioContext)();
      captureContextRef.current = captureCtx;
      await captureCtx.audioWorklet.addModule("/pcm-worklet-processor.js");

      const sourceNode = captureCtx.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(captureCtx, "pcm16-downsampler");
      workletNodeRef.current = workletNode;
      sourceNode.connect(workletNode);

      // 3. Playback AudioContext (Web Audio API at 24 kHz)
      const playbackCtx = new (window.AudioContext || window.webkitAudioContext)();
      playbackContextRef.current = playbackCtx;
      nextPlayTimeRef.current = playbackCtx.currentTime;

      // 4. WebSocket connection to backend
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/live`;

      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      workletNode.port.onmessage = (event) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(event.data);
        }
      };

      ws.onopen = () => {
        const languageHint = location.state?.languageHint || "te";
        ws.send(JSON.stringify({ type: "start", language_hint: languageHint }));
      };

      ws.onmessage = (event) => {
        // Binary frame = 24 kHz PCM16 audio from Gemini Live
        if (event.data instanceof ArrayBuffer) {
          handleIncomingAudio(event.data);
          return;
        }

        // Text frame = JSON control / transcript message
        try {
          const data = JSON.parse(event.data);

          if (data.type === "state") {
            setStatus(data.value);
          } else if (data.type === "interrupted") {
            // Server signaled interruption: clear browser playback queue immediately (barge-in)
            stopAudio();
            setStatus("listening");
          } else if (data.type === "transcript") {
            mergeTranscriptTurn(data.role, data.text, Boolean(data.final));
          } else if (data.type === "turn_complete") {
            finalizeLatestTurn();
            setStatus("listening");
          } else if (data.type === "tool_call") {
            const timeStr = new Date().toLocaleTimeString();
            setToolCalls((prev) => [
              ...prev,
              {
                id: data.id || Math.random().toString(36).substring(2, 9),
                name: data.name,
                args: data.args,
                time: timeStr,
              },
            ]);
          } else if (data.type === "error") {
            setErrorMsg(data.message);
            setStatus("error");
          }
        } catch (err) {
          console.error("Error parsing WS message:", err);
        }
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        setErrorMsg("WebSocket connection failed. Ensure backend is running on port 8000.");
        setStatus("error");
      };

      ws.onclose = () => {
        if (status !== "error") {
          setStatus("disconnected");
        }
      };
    } catch (err) {
      console.error("Failed to start session:", err);
      setErrorMsg(err.message || "Failed to initialize microphone or connection");
      setStatus("error");
      stopSession();
    }
  };

  const handleIncomingAudio = (arrayBuffer) => {
    const playbackCtx = playbackContextRef.current;
    if (!playbackCtx) return;

    const pcm16 = new Int16Array(arrayBuffer);
    if (pcm16.length === 0) return;

    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768.0;
    }

    const audioBuffer = playbackCtx.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);

    const source = playbackCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playbackCtx.destination);

    const currentTime = playbackCtx.currentTime;
    if (nextPlayTimeRef.current < currentTime) {
      nextPlayTimeRef.current = currentTime + 0.05;
    }

    source.start(nextPlayTimeRef.current);
    nextPlayTimeRef.current += audioBuffer.duration;

    activeSourcesRef.current.push(source);
    source.onended = () => {
      activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== source);
    };
  };

  const stopSession = () => {
    stopAudio();

    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (captureContextRef.current) {
      captureContextRef.current.close().catch(() => {});
      captureContextRef.current = null;
    }

    if (playbackContextRef.current) {
      playbackContextRef.current.close().catch(() => {});
      playbackContextRef.current = null;
    }

    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "stop" }));
      }
      wsRef.current.close();
      wsRef.current = null;
    }

    setStatus("disconnected");
  };

  const sendTextTurn = () => {
    if (!typedMessage.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }
    const msg = typedMessage.trim();
    wsRef.current.send(JSON.stringify({ type: "text", text: msg }));
    mergeTranscriptTurn("user", msg, true);
    setTypedMessage("");
  };

  const isConnected = status !== "disconnected" && status !== "error";

  const getStatusColor = () => {
    switch (status) {
      case "listening":
        return "#10b981"; // Emerald green
      case "speaking":
        return "#3b82f6"; // Blue
      case "thinking":
        return "#8b5cf6"; // Purple
      case "connecting":
        return "#f59e0b"; // Amber
      case "reconnecting":
        return "#ea580c"; // Orange
      case "error":
        return "#ef4444"; // Red
      default:
        return "#94a3b8"; // Slate
    }
  };

  const getStatusLabel = () => {
    switch (status) {
      case "listening":
        return "Listening to your voice";
      case "speaking":
        return "Assistant is speaking";
      case "thinking":
        return "Processing & reasoning";
      case "connecting":
        return "Connecting to Gemini Live...";
      case "reconnecting":
        return "Reconnecting session...";
      case "error":
        return "Connection Error";
      default:
        return "Ready to Connect";
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "1.5rem auto", padding: "0 1rem", fontFamily: "sans-serif" }}>
      {/* Voice Panel with Large Mic State Indicator */}
      <div
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: "12px",
          padding: "2rem",
          backgroundColor: "#ffffff",
          boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
          marginBottom: "1.5rem",
          textAlign: "center",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
          {/* Large circular mic indicator */}
          <div
            style={{
              width: 100,
              height: 100,
              borderRadius: "50%",
              backgroundColor: `${getStatusColor()}20`,
              border: `4px solid ${getStatusColor()}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.3s ease",
              boxShadow: isConnected ? `0 0 20px ${getStatusColor()}40` : "none",
            }}
          >
            <span style={{ fontSize: "2.5rem" }}>
              {status === "speaking" ? "🔊" : status === "thinking" ? "⚙️" : status === "reconnecting" ? "🔄" : "🎙️"}
            </span>
          </div>

          <div>
            <h3 style={{ margin: "0.25rem 0", color: "#0f172a", fontSize: "1.35rem" }}>
              {getStatusLabel()}
            </h3>
            <p style={{ margin: 0, color: "#64748b", fontSize: "0.9rem" }}>
              Telugu &bull; Hindi &bull; English &bull; Natural Code-Switching
            </p>
          </div>

          {/* Action Buttons: Connect / Stop Button */}
          <div style={{ display: "flex", gap: "1rem", marginTop: "0.5rem" }}>
            {!isConnected ? (
              <button
                onClick={startSession}
                style={{
                  padding: "0.75rem 1.8rem",
                  fontSize: "1rem",
                  fontWeight: "bold",
                  cursor: "pointer",
                  borderRadius: "8px",
                  border: "none",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  boxShadow: "0 2px 4px rgba(37,99,235,0.2)",
                }}
              >
                🎙️ Start Live Voice
              </button>
            ) : (
              <button
                onClick={stopSession}
                style={{
                  padding: "0.75rem 1.8rem",
                  fontSize: "1rem",
                  fontWeight: "bold",
                  cursor: "pointer",
                  borderRadius: "8px",
                  border: "none",
                  backgroundColor: "#dc2626",
                  color: "#ffffff",
                  boxShadow: "0 2px 4px rgba(220,38,38,0.2)",
                }}
              >
                ⏹️ Stop Assistant
              </button>
            )}

            <button
              onClick={() => {
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({ type: "text", text: "Please call ping tool to test connection" }));
                }
              }}
              disabled={!isConnected}
              style={{
                padding: "0.75rem 1.2rem",
                fontSize: "0.95rem",
                borderRadius: "8px",
                border: "1px solid #cbd5e1",
                backgroundColor: isConnected ? "#f8fafc" : "#e2e8f0",
                color: isConnected ? "#334155" : "#94a3b8",
                cursor: isConnected ? "pointer" : "not-allowed",
              }}
            >
              Test Ping Tool
            </button>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div
          style={{
            padding: "0.8rem",
            marginBottom: "1.5rem",
            backgroundColor: "#fef2f2",
            color: "#991b1b",
            border: "1px solid #fecaca",
            borderRadius: "6px",
          }}
        >
          <strong>Error:</strong> {errorMsg}
        </div>
      )}

      {/* Tool Call Events Card */}
      {toolCalls.length > 0 && (
        <div
          style={{
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            padding: "1rem",
            marginBottom: "1.5rem",
            backgroundColor: "#f8fafc",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h4 style={{ margin: 0, color: "#1e293b" }}>Tool Call Activity</h4>
            <span style={{ fontSize: "0.8rem", color: "#64748b" }}>{toolCalls.length} call(s)</span>
          </div>
          <ul style={{ margin: "0.5rem 0 0 0", paddingLeft: "1.2rem" }}>
            {toolCalls.map((tc) => (
              <li key={tc.id} style={{ margin: "0.25rem 0", fontSize: "0.9rem" }}>
                <strong>[{tc.time}] {tc.name}</strong> &rarr; returned{" "}
                <span style={{ color: "#16a34a", fontWeight: "bold" }}>PONG</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Live Transcripts: Single Line Per Turn */}
      <div
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          padding: "1.25rem",
          marginBottom: "1.5rem",
          backgroundColor: "#ffffff",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <h3 style={{ fontSize: "1.1rem", margin: 0, color: "#0f172a" }}>Live Conversation Transcript</h3>
          <span style={{ fontSize: "0.8rem", color: "#64748b" }}>One line per turn</span>
        </div>

        <div
          style={{
            minHeight: "220px",
            maxHeight: "360px",
            overflowY: "auto",
            backgroundColor: "#f8fafc",
            border: "1px solid #e2e8f0",
            padding: "1rem",
            borderRadius: "6px",
            display: "flex",
            flexDirection: "column",
            gap: "0.75rem",
          }}
        >
          {transcripts.length === 0 ? (
            <p style={{ color: "#94a3b8", fontStyle: "italic", margin: "auto", textAlign: "center" }}>
              Spoken conversation transcripts will appear here turn-by-turn.
            </p>
          ) : (
            transcripts.map((t) => (
              <div
                key={t.id}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: t.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: "80%",
                    padding: "0.6rem 0.9rem",
                    borderRadius: "8px",
                    backgroundColor: t.role === "user" ? "#dbeafe" : "#f1f5f9",
                    color: t.role === "user" ? "#1e40af" : "#0f172a",
                    border: t.role === "user" ? "1px solid #bfdbfe" : "1px solid #e2e8f0",
                    fontSize: "0.95rem",
                    lineHeight: 1.4,
                  }}
                >
                  <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: "0.2rem" }}>
                    <strong>{t.role === "user" ? "You" : "Assistant"}</strong> &bull; {t.time}
                  </div>
                  <div>{t.text}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Typed Input Form */}
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <input
          type="text"
          value={typedMessage}
          placeholder="Type your message here (e.g. 'నేను కుట్టుపని నేర్చుకోవాలనుకుంటున్నాను' or 'Ping')..."
          onChange={(e) => setTypedMessage(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendTextTurn()}
          disabled={!isConnected}
          style={{
            flex: 1,
            padding: "0.6rem 0.9rem",
            fontSize: "0.95rem",
            borderRadius: "6px",
            border: "1px solid #cbd5e1",
          }}
        />
        <button
          onClick={sendTextTurn}
          disabled={!isConnected || !typedMessage.trim()}
          style={{
            padding: "0.6rem 1.25rem",
            fontWeight: "bold",
            cursor: isConnected && typedMessage.trim() ? "pointer" : "not-allowed",
            borderRadius: "6px",
            border: "none",
            backgroundColor: isConnected && typedMessage.trim() ? "#2563eb" : "#cbd5e1",
            color: "#ffffff",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
