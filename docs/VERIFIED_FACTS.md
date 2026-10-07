# Verified Facts for SIH26097 Live Voice Prototype

## 1. Gemini Live API & Models
- **Primary Live Model ID:** `gemini-3.8-live` (configured via env `GEMINI_LIVE_MODEL`, defaulting to `gemini-3.8-live`).
- **Text / Fallback Model ID:** `gemini-2.5-flash` or `gemini-3.8-flash` (via env `GEMINI_TEXT_MODEL`).
- **SDK:** `google-genai` (official Google Gen AI SDK for Python).
- **Session API:** `client.aio.live.connect(model=model, config=config)`.

## 2. Audio Specifications
- **Client Input Audio to Live API:** Raw PCM 16-bit little-endian, mono, 16,000 Hz (`audio/pcm;rate=16000`).
- **Model Output Audio from Live API:** Raw PCM 16-bit little-endian, mono, 24,000 Hz (`audio/pcm;rate=24000`).
- **Capture:** Browser `getUserMedia` with `{ echoCancellation: true, noiseSuppression: true, autoGainControl: true }`.
- **Downsampling:** AudioWorklet processor running in audio context, downsampling from native hardware sample rate (typically 44.1 kHz or 48 kHz) to 16 kHz mono PCM16 bytes.
- **Playback:** Web Audio API `AudioContext` running at 24 kHz (or buffer playback scheduling at 24 kHz).

## 3. Communication Protocol (`/ws/live`)
- **Browser to Backend:**
  - Binary frames: raw PCM16 mono 16 kHz chunks.
  - JSON frames: `{"type": "start", "language_hint": "te|hi|en"}`, `{"type": "stop"}`.
- **Backend to Browser:**
  - Binary frames: raw PCM16 mono 24 kHz audio chunks from Gemini.
  - JSON frames:
    - `{"type": "state", "value": "connecting|listening|speaking|thinking|error"}`
    - `{"type": "transcript", "role": "user|assistant", "text": "...", "final": bool}`
    - `{"type": "tool_call", "name": "ping", "args": {...}}`
    - `{"type": "error", "message": "..."}`

## 4. Function Calling / Tools
- In `LiveConnectConfig`, declare `types.Tool(function_declarations=[...])`.
- When `msg.tool_call` arrives:
  - Backend extracts `tool_call.function_calls`.
  - For `ping`: backend executes dummy ping handler, notifies frontend via `{"type": "tool_call", "name": "ping", "args": ...}`, and sends tool response back to Gemini via `session.send_tool_response(...)`.
