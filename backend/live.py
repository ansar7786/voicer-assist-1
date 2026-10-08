"""
Live session manager for Gemini Live API (Phase 4).
Extends Phase 3 with:
- Per-WebSocket SessionState (session_store.py)
- update_profile and confirm_profile tool routing (tools.py)
- profile_update events pushed to the browser after every successful update
- Blocklist applied inside tool handlers (no caste/religion/address/ID)
- Transcripts NEVER stored in session or DB
- Audio NEVER written to disk
- Logs: event types and timings only
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

from backend.session_store import create_session, delete_session, SessionState, get_session
from backend.tools import (
    handle_ping,
    handle_update_profile,
    handle_confirm_profile,
    PING_DECLARATION,
    UPDATE_PROFILE_DECLARATION,
    CONFIRM_PROFILE_DECLARATION,
)

# ---------------------------------------------------------------------------
# Audit logger  — event types and timings ONLY
# ---------------------------------------------------------------------------
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
        raise ValueError("GEMINI_LIVE_MODEL is not set in .env")
    return model


def load_system_instruction() -> str:
    if SYSTEM_INSTRUCTION_PATH.exists():
        with open(SYSTEM_INSTRUCTION_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    return (
        "You are a friendly voice assistant helping a person in rural India explore "
        "livelihood and skill training options. You speak and understand Telugu, Hindi, "
        "and English naturally. Keep replies short (1–2 sentences). "
        "Call update_profile silently whenever the user states a clear fact about "
        "themselves (education, skills, work experience, interests, mobility, income urgency). "
        "After you have gathered enough information, read the profile back in simple words "
        "and call confirm_profile once the user says yes."
    )


def _make_function_declaration(d: dict) -> types.FunctionDeclaration:
    """Convert our declaration dict to a FunctionDeclaration with behavior wired."""
    kwargs = {
        "name": d["name"],
        "description": d["description"],
        "parameters": d.get("parameters"),
    }
    if "behavior" in d and d["behavior"]:
        kwargs["behavior"] = d["behavior"]
    return types.FunctionDeclaration(**kwargs)


def get_live_config(handle: Optional[str] = None) -> types.LiveConnectConfig:
    sys_text = load_system_instruction()

    session_resumption = (
        types.SessionResumptionConfig(handle=handle)
        if handle
        else types.SessionResumptionConfig()
    )

    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=sys_text)]),
        tools=[
            types.Tool(
                function_declarations=[
                    _make_function_declaration(PING_DECLARATION),
                    _make_function_declaration(UPDATE_PROFILE_DECLARATION),
                    _make_function_declaration(CONFIRM_PROFILE_DECLARATION),
                ]
            )
        ],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()
        ),
        session_resumption=session_resumption,
    )


# ---------------------------------------------------------------------------
# Persist profile to DB (profile_json + edit_log rows only)
# ---------------------------------------------------------------------------
def _persist_profile(session: SessionState):
    """Write profile JSON and new edit_log entries to the database.
    Transcripts are NEVER written."""
    try:
        from backend.db import get_db_connection
        import json as _json

        conn = get_db_connection()
        cur = conn.cursor()
        now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Upsert session row – only profile_json; transcript_json stays NULL always
        cur.execute(
            """
            INSERT INTO sessions (id, created_at, language, transcript_json, profile_json,
                                  constraints_json, consent_official_view)
            VALUES (?, ?, ?, NULL, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET
                profile_json = excluded.profile_json,
                constraints_json = excluded.constraints_json
            """,
            (
                session.session_id,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(session.created_at)),
                session.language,
                session.to_profile_json(),
                _json.dumps(session.constraints, ensure_ascii=False),
            ),
        )

        # Write any unwritten field_history rows as edit_log entries
        for entry in session.field_history:
            cur.execute(
                """
                INSERT OR IGNORE INTO edit_log
                    (session_id, field, old_value, new_value, actor, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    entry["field"],
                    _json.dumps(entry["old"], ensure_ascii=False) if entry["old"] is not None else None,
                    _json.dumps(entry["new"], ensure_ascii=False),
                    entry.get("source", "voice"),
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry["ts"])),
                ),
            )

        conn.commit()
        conn.close()
        logger.info("EVENT: profile_persisted | session: %s | time: %.3f",
                    session.session_id, time.time())
    except Exception:
        logger.error("EVENT: profile_persist_error | time: %.3f", time.time())


# ---------------------------------------------------------------------------
# Error classification and watchdog helpers
# ---------------------------------------------------------------------------
def classify_live_error(exc: Exception) -> dict:
    exc_str = str(exc).lower()

    # 1. Quota exceeded (429, resource_exhausted, quota)
    if "429" in exc_str or "resource_exhausted" in exc_str or "quota" in exc_str:
        return {
            "code": "quota_exceeded",
            "message": "Voice service quota reached. Please try typed input or retry shortly.",
            "fallback": "typed",
        }
    # 2. Auth failed (bad key, 401, 403, api_key, unauthenticated, permission_denied)
    if (
        "401" in exc_str
        or "403" in exc_str
        or "auth" in exc_str
        or "permission_denied" in exc_str
        or "unauthenticated" in exc_str
        or "api_key" in exc_str
    ):
        return {
            "code": "auth_failed",
            "message": "Authentication failed. Please verify API configuration.",
            "fallback": "retry",
        }
    # 3. Session expired (session_expired, resumption handle invalid/expired)
    if "session_expired" in exc_str or "expired" in exc_str or ("handle" in exc_str and "invalid" in exc_str):
        return {
            "code": "session_expired",
            "message": "Voice session expired. Please retry to reconnect.",
            "fallback": "retry",
        }
    # 4. Model unavailable (404, 503, unavailable, not_found)
    if "503" in exc_str or "404" in exc_str or "unavailable" in exc_str or "not_found" in exc_str:
        return {
            "code": "model_unavailable",
            "message": "Live voice model is currently unavailable. Please try typed input.",
            "fallback": "typed",
        }
    # 5. Connection lost
    if (
        isinstance(exc, (ConnectionError, EOFError, asyncio.IncompleteReadError, WebSocketDisconnect))
        or "connection" in exc_str
        or "disconnect" in exc_str
        or "reset" in exc_str
        or "closed" in exc_str
        or "broken" in exc_str
    ):
        return {
            "code": "connection_lost",
            "message": "Connection to voice service was lost. Please retry.",
            "fallback": "retry",
        }
    # Default fallback
    return {
        "code": "connection_lost",
        "message": "Connection to voice service was interrupted. Please retry.",
        "fallback": "retry",
    }


def get_no_reply_timeout() -> float:
    env_val = os.getenv("LIVE_NO_REPLY_TIMEOUT_SECONDS")
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass
    try:
        import yaml
        cfg_path = Path(__file__).resolve().parent / "engine_config.yaml"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                timeout = cfg.get("live_session", {}).get("no_reply_timeout_seconds")
                if timeout is not None:
                    return float(timeout)
    except Exception:
        pass
    return 10.0


# ---------------------------------------------------------------------------
# Main WebSocket handler
# ---------------------------------------------------------------------------
async def handle_live_session(websocket: WebSocket):
    api_key = get_gemini_api_key()
    try:
        live_model = get_gemini_live_model()
    except ValueError:
        logger.error("EVENT: error | code: model_unavailable | time: %.3f", time.time())
        await websocket.send_json({
            "type": "error",
            "code": "model_unavailable",
            "message": "Live model configuration is missing or invalid.",
            "fallback": "retry",
        })
        await websocket.send_json({"type": "state", "value": "error"})
        await websocket.close()
        return

    if not api_key:
        logger.error("EVENT: error | code: auth_failed | time: %.3f", time.time())
        await websocket.send_json({
            "type": "error",
            "code": "auth_failed",
            "message": "Authentication failed. GEMINI_API_KEY is not set in .env",
            "fallback": "retry",
        })
        await websocket.send_json({"type": "state", "value": "error"})
        await websocket.close()
        return

    # Reuse session if requested and present, else create new
    req_session_id = websocket.query_params.get("session_id")
    if req_session_id and get_session(req_session_id):
        session = get_session(req_session_id)
        logger.info("EVENT: session_resumed | id: %s | time: %.3f", session.session_id, time.time())
    else:
        session = create_session(language="te")

    # Register push callback so tool handlers can emit events to browser
    async def push_to_browser(event_type: str, payload: dict):
        try:
            await websocket.send_json({"type": event_type, **payload})
        except Exception:
            pass

    session.register_push(push_to_browser)

    # Send session_id to the browser so the UI can use it for PATCH requests
    await websocket.send_json({"type": "session_id", "value": session.session_id})

    # If the session already had profile fields, send profile_update immediately to hydrate client
    if session.profile:
        profile_export = {
            k: v for k, v in session.profile.items()
            if not k.startswith("_")
        }
        confidence_map = session.profile.get("_confidence", {})
        await websocket.send_json({
            "type": "profile_update",
            "profile": profile_export,
            "confidence": confidence_map,
            "confirmed": session.confirmed,
        })

    client = genai.Client(api_key=api_key)
    session_handle: Optional[str] = None
    client_disconnected = False

    client_queue: asyncio.Queue = asyncio.Queue()

    async def client_reader():
        nonlocal client_disconnected, session
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
                        lang = data.get("language_hint", "te")
                        session.language = lang
                        sid = data.get("session_id")
                        if sid and sid != session.session_id and get_session(sid):
                            session = get_session(sid)
                            session.register_push(push_to_browser)
                            logger.info("EVENT: session_rebound | id: %s | time: %.3f", session.session_id, time.time())
                        logger.info("EVENT: client_start | time: %.3f", time.time())
        except (WebSocketDisconnect, asyncio.CancelledError):
            client_disconnected = True
            await client_queue.put({"type": "disconnect"})
        except Exception:
            logger.error("EVENT: client_reader_error | time: %.3f", time.time())
            client_disconnected = True
            await client_queue.put({"type": "disconnect"})

    watchdog_timeout = get_no_reply_timeout()
    watchdog_task: Optional[asyncio.Task] = None

    async def _watchdog_timer():
        try:
            await asyncio.sleep(watchdog_timeout)
            logger.error("EVENT: error | code: no_reply | time: %.3f", time.time())
            await websocket.send_json({
                "type": "error",
                "code": "no_reply",
                "message": "Assistant took too long to respond. Please try speaking again or use typed input.",
                "fallback": "typed",
            })
            await websocket.send_json({"type": "state", "value": "error"})
        except asyncio.CancelledError:
            pass

    def start_watchdog():
        nonlocal watchdog_task
        if watchdog_task and not watchdog_task.done():
            watchdog_task.cancel()
        watchdog_task = asyncio.create_task(_watchdog_timer())

    def reset_watchdog():
        nonlocal watchdog_task
        if watchdog_task and not watchdog_task.done():
            watchdog_task.cancel()
        watchdog_task = None

    reader_task = asyncio.create_task(client_reader())

    try:
        while not client_disconnected:
            config = get_live_config(handle=session_handle)
            state_val = "reconnecting" if session_handle else "connecting"
            logger.info("EVENT: %s | time: %.3f", state_val, time.time())
            await websocket.send_json({"type": "state", "value": state_val})

            should_reconnect = False

            try:
                async with client.aio.live.connect(model=live_model, config=config) as live_session:
                    logger.info("EVENT: session_connected | time: %.3f", time.time())
                    await websocket.send_json({"type": "state", "value": "listening"})

                    async def send_to_gemini():
                        nonlocal client_disconnected, should_reconnect
                        while True:
                            item = await client_queue.get()
                            itype = item.get("type")
                            if itype == "audio":
                                await live_session.send_realtime_input(
                                    audio=types.Blob(
                                        data=item["data"],
                                        mime_type="audio/pcm;rate=16000",
                                    )
                                )
                            elif itype == "text":
                                start_watchdog()
                                logger.info("EVENT: send_client_content | time: %.3f", time.time())
                                await live_session.send_client_content(
                                    turns=types.Content(
                                        role="user",
                                        parts=[types.Part(text=item["data"])],
                                    ),
                                    turn_complete=True,
                                )
                            elif itype in ("stop", "disconnect"):
                                client_disconnected = True
                                break

                    async def receive_from_gemini():
                        nonlocal session_handle, should_reconnect
                        async for response in live_session.receive():
                            # Session resumption handle
                            if response.session_resumption_update:
                                sru = response.session_resumption_update
                                if sru.new_handle:
                                    session_handle = sru.new_handle
                                    logger.info("EVENT: resumption_handle_updated | time: %.3f", time.time())

                            # GoAway
                            if response.go_away:
                                logger.info("EVENT: go_away_received | time: %.3f", time.time())
                                await websocket.send_json({"type": "state", "value": "reconnecting"})
                                should_reconnect = True
                                break

                            # Server content
                            sc = response.server_content
                            if sc:
                                if sc.interrupted:
                                    logger.info("EVENT: server_interrupted | time: %.3f", time.time())
                                    await websocket.send_json({"type": "interrupted"})
                                    await websocket.send_json({"type": "state", "value": "listening"})

                                if sc.input_transcription and sc.input_transcription.text:
                                    is_final = bool(sc.input_transcription.finished)
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "role": "user",
                                        "text": sc.input_transcription.text,
                                        "final": is_final,
                                    })
                                    if is_final:
                                        start_watchdog()

                                if sc.output_transcription and sc.output_transcription.text:
                                    reset_watchdog()
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "role": "assistant",
                                        "text": sc.output_transcription.text,
                                        "final": bool(sc.output_transcription.finished),
                                    })

                                if sc.model_turn and sc.model_turn.parts:
                                    reset_watchdog()
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

                            # Tool calls
                            tc = response.tool_call
                            if tc and tc.function_calls:
                                reset_watchdog()
                                logger.info("EVENT: tool_call_received | count: %d | time: %.3f",
                                            len(tc.function_calls), time.time())
                                has_blocking = any(fc.name in ("confirm_profile", "ping") for fc in tc.function_calls)
                                if has_blocking:
                                    await websocket.send_json({"type": "state", "value": "thinking"})
                                tool_responses = []

                                for fc in tc.function_calls:
                                    args = fc.args or {}
                                    fn_name = fc.name
                                    has_tool_error = False

                                    try:
                                        # Dispatch
                                        if fn_name == "ping":
                                            resp_data = handle_ping(args)
                                            # Only notify browser for ping (visible tool)
                                            await websocket.send_json({
                                                "type": "tool_call",
                                                "name": fn_name,
                                                "args": args,
                                                "id": fc.id,
                                                "timestamp": time.time(),
                                            })

                                        elif fn_name == "update_profile":
                                            resp_data = handle_update_profile(args, session)
                                            if resp_data.get("ok"):
                                                # Push profile_update event to browser
                                                profile_export = {
                                                    k: v for k, v in session.profile.items()
                                                    if not k.startswith("_")
                                                }
                                                confidence_map = session.profile.get("_confidence", {})
                                                await session.push("profile_update", {
                                                    "profile": profile_export,
                                                    "confidence": confidence_map,
                                                    "confirmed": session.confirmed,
                                                })
                                                # Persist to DB
                                                _persist_profile(session)

                                        elif fn_name == "confirm_profile":
                                            resp_data = handle_confirm_profile(args, session)
                                            if resp_data.get("ok"):
                                                profile_export = {
                                                    k: v for k, v in session.profile.items()
                                                    if not k.startswith("_")
                                                }
                                                confidence_map = session.profile.get("_confidence", {})
                                                await session.push("profile_update", {
                                                    "profile": profile_export,
                                                    "confidence": confidence_map,
                                                    "confirmed": True,
                                                })
                                                _persist_profile(session)

                                        else:
                                            resp_data = {
                                                "error": "unknown_tool",
                                                "name": fn_name,
                                                "recoverable": True,
                                            }

                                        if isinstance(resp_data, dict) and resp_data.get("error") == "tool_error":
                                            has_tool_error = True
                                    except Exception:
                                        has_tool_error = True
                                        resp_data = {
                                            "error": "tool_error",
                                            "message": "Tool execution failed recoverably",
                                            "recoverable": True,
                                        }

                                    if has_tool_error:
                                        logger.error("EVENT: error | code: tool_error | time: %.3f", time.time())
                                        try:
                                            await websocket.send_json({
                                                "type": "error",
                                                "code": "tool_error",
                                                "message": "A tool encountered an error during execution.",
                                                "fallback": "retry",
                                            })
                                        except Exception:
                                            pass

                                    tool_responses.append(
                                        types.FunctionResponse(
                                            name=fn_name,
                                            id=fc.id,
                                            response=resp_data,
                                            scheduling=types.FunctionResponseScheduling.SILENT if fn_name == "update_profile" else None,
                                        )
                                    )

                                if tool_responses:
                                    await live_session.send_tool_response(
                                        function_responses=tool_responses
                                    )
                                    if not has_blocking:
                                        await websocket.send_json({"type": "state", "value": "listening"})

                    sender_t = asyncio.create_task(send_to_gemini())
                    receiver_t = asyncio.create_task(receive_from_gemini())

                    done, pending = await asyncio.wait(
                        [sender_t, receiver_t],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                    for t in done:
                        if t.exception():
                            raise t.exception()

            except Exception as e:
                err_info = classify_live_error(e)
                logger.error("EVENT: error | code: %s | time: %.3f", err_info["code"], time.time())
                if client_disconnected:
                    break
                try:
                    await websocket.send_json({
                        "type": "error",
                        "code": err_info["code"],
                        "message": err_info["message"],
                        "fallback": err_info["fallback"],
                    })
                    await websocket.send_json({"type": "state", "value": "error"})
                except Exception:
                    pass
                break

            if not should_reconnect or client_disconnected:
                break

    finally:
        reset_watchdog()
        reader_task.cancel()
        # Final profile persistence on disconnect
        if session.profile:
            _persist_profile(session)
        logger.info("EVENT: session_closed | time: %.3f", time.time())
        try:
            await websocket.close()
        except Exception:
            pass

