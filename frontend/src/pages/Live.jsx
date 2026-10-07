import { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";

export default function Live() {
  const location = useLocation();
  const [status, setStatus] = useState("disconnected"); // disconnected, connecting, listening, speaking, thinking, error
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
        // ignore already stopped
      }
    });
    activeSourcesRef.current = [];
    if (playbackContextRef.current) {
      nextPlayTimeRef.current = playbackContextRef.current.currentTime;
    }
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

      // 2. Capture AudioContext & AudioWorklet
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

      // 4. WebSocket connection to backend (proxied by Vite or direct)
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
        console.log("WebSocket connected to", wsUrl);
        const languageHint = location.state?.languageHint || "te";
        ws.send(JSON.stringify({ type: "start", language_hint: languageHint }));
      };

      ws.onmessage = (event) => {
        // Binary frame = 24 kHz PCM16 audio from Gemini
        if (event.data instanceof ArrayBuffer) {
          handleIncomingAudio(event.data);
          return;
        }

        // Text frame = JSON control/transcript message
        try {
          const data = JSON.parse(event.data);

          if (data.type === "state") {
            setStatus(data.value);
          } else if (data.type === "interrupted") {
            stopAudio();
            setStatus("listening");
          } else if (data.type === "transcript") {
            const timeStr = new Date().toLocaleTimeString();
            setTranscripts((prev) => [
              ...prev,
              {
                id: Math.random().toString(36).substring(2, 9),
                role: data.role,
                text: data.text,
                final: data.final,
                time: timeStr,
              },
            ]);
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
        console.log("WebSocket closed");
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

    // Convert PCM16 to Float32 [-1.0, 1.0]
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768.0;
    }

    // Output from Gemini Live is 24,000 Hz mono
    const audioBuffer = playbackCtx.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);

    const source = playbackCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playbackCtx.destination);

    const currentTime = playbackCtx.currentTime;
    if (nextPlayTimeRef.current < currentTime) {
      nextPlayTimeRef.current = currentTime + 0.05; // 50ms buffer
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
    wsRef.current.send(JSON.stringify({ type: "text", text: typedMessage }));
    setTranscripts((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substring(2, 9),
        role: "user",
        text: typedMessage,
        final: true,
        time: new Date().toLocaleTimeString(),
      },
    ]);
    setTypedMessage("");
  };

  return (
    <div style={{ maxWidth: 880, margin: "1.5rem auto", padding: "0 1rem", fontFamily: "sans-serif" }}>
      <h2 style={{ margin: "0 0 0.5rem 0", color: "#0f172a" }}>Live Voice Console</h2>
      <p style={{ color: "#64748b", margin: "0 0 1.5rem 0" }}>
        Live Gemini Audio Session (16 kHz PCM Mic In &rarr; Gemini Live &rarr; 24 kHz PCM Audio Out)
      </p>

      {/* Connection Controls & State Indicator */}
      <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem" }}>
        {status === "disconnected" || status === "error" ? (
          <button
            onClick={startSession}
            style={{
              padding: "0.6rem 1.2rem",
              fontSize: "1rem",
              fontWeight: "bold",
              cursor: "pointer",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "#2563eb",
              color: "#ffffff",
            }}
          >
            Connect &amp; Start Mic
          </button>
        ) : (
          <button
            onClick={stopSession}
            style={{
              padding: "0.6rem 1.2rem",
              fontSize: "1rem",
              fontWeight: "bold",
              cursor: "pointer",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "#dc2626",
              color: "#ffffff",
            }}
          >
            Disconnect &amp; Stop Mic
          </button>
        )}

        {/* State Indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <strong>State:</strong>
          <span
            style={{
              display: "inline-block",
              padding: "0.3rem 0.8rem",
              borderRadius: "4px",
              fontWeight: "bold",
              textTransform: "uppercase",
              fontSize: "0.85rem",
              backgroundColor:
                status === "listening"
                  ? "#d4edda"
                  : status === "speaking"
                  ? "#cce5ff"
                  : status === "connecting"
                  ? "#fff3cd"
                  : status === "thinking"
                  ? "#e2e3e5"
                  : status === "error"
                  ? "#f8d7da"
                  : "#eee",
              color:
                status === "listening"
                  ? "#155724"
                  : status === "speaking"
                  ? "#004085"
                  : status === "connecting"
                  ? "#856404"
                  : status === "thinking"
                  ? "#383d41"
                  : status === "error"
                  ? "#721c24"
                  : "#333",
            }}
          >
            {status}
          </span>
        </div>
      </div>

      {errorMsg && (
        <div
          style={{
            padding: "0.8rem",
            marginBottom: "1rem",
            backgroundColor: "#f8d7da",
            color: "#721c24",
            border: "1px solid #f5c6cb",
            borderRadius: "4px",
          }}
        >
          <strong>Error:</strong> {errorMsg}
        </div>
      )}

      {/* Dummy Tool (ping) Section */}
      <div
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: "6px",
          padding: "1rem",
          marginBottom: "1.5rem",
          backgroundColor: "#f8fafc",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ fontSize: "1.1rem", margin: 0, color: "#1e293b" }}>Registered Tool: ping</h3>
          <button
            onClick={() => {
              if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: "text", text: "Please call the ping tool with message test" }));
              }
            }}
            disabled={status !== "listening" && status !== "speaking"}
            style={{ padding: "0.4rem 0.8rem", cursor: "pointer", borderRadius: "4px" }}
          >
            Trigger ping tool via text
          </button>
        </div>
        <p style={{ fontSize: "0.85rem", color: "#64748b", margin: "0.5rem 0" }}>
          Speak <em>&quot;Please ping&quot;</em> or <em>&quot;Test ping tool&quot;</em> into your mic, or use the trigger button above.
        </p>
        <div style={{ marginTop: "0.5rem" }}>
          <strong>Tool Call Events ({toolCalls.length}):</strong>
          {toolCalls.length === 0 ? (
            <p style={{ color: "#94a3b8", fontStyle: "italic", margin: "0.25rem 0" }}>
              No tool calls yet. Ask Gemini to call &apos;ping&apos;.
            </p>
          ) : (
            <ul style={{ margin: "0.5rem 0", paddingLeft: "1.2rem" }}>
              {toolCalls.map((tc) => (
                <li key={tc.id} style={{ margin: "0.25rem 0" }}>
                  <strong>[{tc.time}] Tool Called:</strong> <code>{tc.name}</code> |{" "}
                  <strong>Args:</strong> <code>{JSON.stringify(tc.args)}</code> &rarr; returned{" "}
                  <span style={{ color: "#16a34a", fontWeight: "bold" }}>PONG</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Live Input and Output Transcripts */}
      <div
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: "6px",
          padding: "1rem",
          marginBottom: "1.5rem",
          backgroundColor: "#ffffff",
        }}
      >
        <h3 style={{ fontSize: "1.1rem", margin: "0 0 0.8rem 0", color: "#1e293b" }}>Live Transcripts</h3>
        <div
          style={{
            height: "240px",
            overflowY: "auto",
            backgroundColor: "#f8fafc",
            border: "1px solid #e2e8f0",
            padding: "0.75rem",
            borderRadius: "4px",
          }}
        >
          {transcripts.length === 0 ? (
            <p style={{ color: "#94a3b8", fontStyle: "italic", margin: 0 }}>
              Transcripts will appear here when you or the assistant speak.
            </p>
          ) : (
            transcripts.map((t) => (
              <div
                key={t.id}
                style={{
                  marginBottom: "0.5rem",
                  color: t.role === "user" ? "#1e40af" : "#166534",
                }}
              >
                <span style={{ fontSize: "0.8rem", color: "#94a3b8", marginRight: "0.5rem" }}>
                  [{t.time}]
                </span>
                <strong>{t.role === "user" ? "You (Input):" : "Gemini (Output):"}</strong>{" "}
                <span>{t.text}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Typed Input Fallback */}
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <input
          type="text"
          value={typedMessage}
          placeholder="Type a message (e.g., 'Say hello in Telugu' or 'Ping')..."
          onChange={(e) => setTypedMessage(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendTextTurn()}
          disabled={status !== "listening" && status !== "speaking"}
          style={{ flex: 1, padding: "0.5rem", fontSize: "0.95rem", borderRadius: "4px", border: "1px solid #cbd5e1" }}
        />
        <button
          onClick={sendTextTurn}
          disabled={status !== "listening" && status !== "speaking"}
          style={{ padding: "0.5rem 1rem", cursor: "pointer", borderRadius: "4px" }}
        >
          Send Text
        </button>
      </div>
    </div>
  );
}
