"""
Live session manager for Gemini Live API (Phase 3).
Features:
- Session resumption with in-memory handle tracking.
- GoAway handling with graceful reconnection using session handle.
- Context window compression with sliding window.
- Audio input (PCM16 16kHz) and audio output (PCM16 24kHz) streaming.
- Input and output audio transcription.
- Typed text input via send_client_content(turn_complete=True).
- Server interruption signaling for browser playback queue clearing (barge-in).
- State events: connecting, listening, speaking, thinking, reconnecting, error.
- System instruction loaded from backend/system_instruction.txt.
- Privacy compliance: Logs contain ONLY event types and timings; never transcripts or audio.
- Audio is NEVER written to disk.
"""
import os
import time
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

# Setup audit logger for timings and event types ONLY
logger = logging.getLogger("voicer_live")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
SYSTEM_INSTRUCTION_PATH = Path(__file__).resolve().parent / "system_instruction.txt"

load_dotenv(dotenv_path=ENV_PATH)

def get_gemini_api_key() -> str:
    load_dotenv(dotenv_path=ENV_PATH)
    return os.getenv("GEMINI_API_KEY", "").strip()

def get_gemini_live_model() -> str:
    load_dotenv(dotenv_path=ENV_PATH)
    model = os.getenv("GEMINI_LIVE_MODEL", "").strip()
    if not model:
        raise ValueError("GEMINI_LIVE_MODEL environment variable is not set. Please set it in .env.")
    return model

def load_system_instruction() -> str:
    if SYSTEM_INSTRUCTION_PATH.exists():
        with open(SYSTEM_INSTRUCTION_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    return (
        "You are a friendly, conversational voice assistant helping a person in India. "
        "You speak and understand Telugu, Hindi, and English. Keep replies natural and concise (1-2 sentences). "
        "If the user says ping or mentions testing tools, call the ping tool immediately."
    )

def get_live_config(handle: Optional[str] = None) -> types.LiveConnectConfig:
    ping_tool = types.FunctionDeclaration(
        name="ping",
        description="A dummy tool for health and connectivity verification. Call this tool whenever the user says ping or asks to test tools.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "message": {
                    "type": "STRING",
                    "description": "Optional ping message or payload from user",
                }
            },
        },
    )

    sys_text = load_system_instruction()

    session_resumption = (
        types.SessionResumptionConfig(handle=handle)
        if handle
        else types.SessionResumptionConfig()
    )

    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=sys_text)]
        ),
        tools=[types.Tool(function_declarations=[ping_tool])],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()
        ),
        session_resumption=session_resumption,
    )

async def handle_live_session(websocket: WebSocket):
    api_key = get_gemini_api_key()
    try:
        live_model = get_gemini_live_model()
    except ValueError as e:
        logger.error("EVENT: config_error | time: %.3f", time.time())
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.send_json({"type": "state", "value": "error"})
        await websocket.close()
        return

    if not api_key:
        logger.error("EVENT: auth_missing | time: %.3f", time.time())
        await websocket.send_json({
            "type": "error",
            "message": "GEMINI_API_KEY is not set in .env. Please configure your API key.",
        })
        await websocket.send_json({"type": "state", "value": "error"})
        await websocket.close()
        return

    client = genai.Client(api_key=api_key)
    session_handle: Optional[str] = None
    client_disconnected = False

    # Incoming message queue from WebSocket client
    client_queue = asyncio.Queue()

    async def client_reader():
        nonlocal client_disconnected
        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message and message["bytes"]:
                    await client_queue.put({"type": "audio", "data": message["bytes"]})
                elif "text" in message and message["text"]:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")
                    if msg_type == "stop":
                        logger.info("EVENT: client_stop | time: %.3f", time.time())
                        await client_queue.put({"type": "stop"})
                        break
                    elif msg_type == "text":
                        text_val = data.get("text", "").strip()
                        if text_val:
                            await client_queue.put({"type": "text", "data": text_val})
                    elif msg_type == "start":
                        logger.info("EVENT: client_start | time: %.3f", time.time())
        except (WebSocketDisconnect, asyncio.CancelledError):
            client_disconnected = True
            await client_queue.put({"type": "disconnect"})
        except Exception as e:
            logger.error("EVENT: client_reader_error | time: %.3f", time.time())
            client_disconnected = True
            await client_queue.put({"type": "disconnect"})

    reader_task = asyncio.create_task(client_reader())

    try:
        while not client_disconnected:
            config = get_live_config(handle=session_handle)
            state_val = "reconnecting" if session_handle else "connecting"
            logger.info("EVENT: %s | handle_present: %s | time: %.3f", state_val, bool(session_handle), time.time())
            await websocket.send_json({"type": "state", "value": state_val})

            should_reconnect = False

            try:
                async with client.aio.live.connect(model=live_model, config=config) as session:
                    logger.info("EVENT: session_connected | time: %.3f", time.time())
                    await websocket.send_json({"type": "state", "value": "listening"})

                    async def send_to_gemini():
                        nonlocal client_disconnected, should_reconnect
                        while True:
                            item = await client_queue.get()
                            itype = item.get("type")

                            if itype == "audio":
                                pcm_bytes = item["data"]
                                await session.send_realtime_input(
                                    audio=types.Blob(
                                        data=pcm_bytes,
                                        mime_type="audio/pcm;rate=16000",
                                    )
                                )
                            elif itype == "text":
                                text_val = item["data"]
                                logger.info("EVENT: send_client_content | time: %.3f", time.time())
                                await session.send_client_content(
                                    turns=types.Content(
                                        role="user",
                                        parts=[types.Part(text=text_val)],
                                    ),
                                    turn_complete=True,
                                )
                            elif itype in ("stop", "disconnect"):
                                client_disconnected = True
                                break

                    async def receive_from_gemini():
                        nonlocal session_handle, should_reconnect
                        async for response in session.receive():
                            # 1. Session Resumption Update
                            if response.session_resumption_update:
                                sru = response.session_resumption_update
                                if sru.new_handle:
                                    session_handle = sru.new_handle
                                    logger.info("EVENT: resumption_handle_updated | time: %.3f", time.time())

                            # 2. GoAway notification handling
                            if response.go_away:
                                logger.info("EVENT: go_away_received | time: %.3f", time.time())
                                await websocket.send_json({"type": "state", "value": "reconnecting"})
                                should_reconnect = True
                                break

                            # 3. Server Content
                            sc = response.server_content
                            if sc:
                                if sc.interrupted:
                                    logger.info("EVENT: server_interrupted | time: %.3f", time.time())
                                    await websocket.send_json({"type": "interrupted"})
                                    await websocket.send_json({"type": "state", "value": "listening"})

                                if sc.input_transcription and sc.input_transcription.text:
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "role": "user",
                                        "text": sc.input_transcription.text,
                                        "final": bool(sc.input_transcription.finished),
                                    })

                                if sc.output_transcription and sc.output_transcription.text:
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "role": "assistant",
                                        "text": sc.output_transcription.text,
                                        "final": bool(sc.output_transcription.finished),
                                    })

                                if sc.model_turn and sc.model_turn.parts:
                                    for part in sc.model_turn.parts:
                                        if part.inline_data and part.inline_data.data:
                                            await websocket.send_json({"type": "state", "value": "speaking"})
                                            await websocket.send_bytes(part.inline_data.data)
                                        if part.text:
                                            await websocket.send_json({
                                                "type": "transcript",
                                                "role": "assistant",
                                                "text": part.text,
                                                "final": False,
                                            })

                                if sc.turn_complete:
                                    await websocket.send_json({"type": "turn_complete"})
                                    await websocket.send_json({"type": "state", "value": "listening"})

                            # 4. Tool calls
                            tc = response.tool_call
                            if tc and tc.function_calls:
                                logger.info("EVENT: tool_call_received | time: %.3f", time.time())
                                await websocket.send_json({"type": "state", "value": "thinking"})
                                responses = []
                                for fc in tc.function_calls:
                                    args = fc.args or {}
                                    await websocket.send_json({
                                        "type": "tool_call",
                                        "name": fc.name,
                                        "args": args,
                                        "id": fc.id,
                                        "timestamp": time.time(),
                                    })

                                    if fc.name == "ping":
                                        resp_data = {"status": "pong", "message": args.get("message", "pong")}
                                    else:
                                        resp_data = {"status": "unsupported_tool"}

                                    responses.append(
                                        types.FunctionResponse(
                                            name=fc.name,
                                            id=fc.id,
                                            response=resp_data,
                                        )
                                    )

                                if responses:
                                    await session.send_tool_response(function_responses=responses)

                    sender_t = asyncio.create_task(send_to_gemini())
                    receiver_t = asyncio.create_task(receive_from_gemini())

                    done, pending = await asyncio.wait(
                        [sender_t, receiver_t],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for t in pending:
                        t.cancel()

            except Exception as e:
                logger.error("EVENT: session_exception | time: %.3f", time.time())
                if client_disconnected:
                    break
                if session_handle:
                    should_reconnect = True
                    await asyncio.sleep(0.5)
                else:
                    await websocket.send_json({"type": "error", "message": str(e)})
                    await websocket.send_json({"type": "state", "value": "error"})
                    break

            if not should_reconnect or client_disconnected:
                break

    finally:
        reader_task.cancel()
        logger.info("EVENT: session_closed | time: %.3f", time.time())
        try:
            await websocket.close()
        except Exception:
            pass
