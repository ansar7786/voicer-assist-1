import os
import time
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

# Explicitly resolve the project-root .env path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

def get_gemini_api_key() -> str:
    load_dotenv(dotenv_path=ENV_PATH)
    return os.getenv("GEMINI_API_KEY", "").strip()

def get_gemini_live_model() -> str:
    load_dotenv(dotenv_path=ENV_PATH)
    return os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live").strip() or "gemini-3.8-live"

GEMINI_API_KEY = get_gemini_api_key()
GEMINI_LIVE_MODEL = get_gemini_live_model()

def get_live_config() -> types.LiveConnectConfig:
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

    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[
                types.Part(
                    text=(
                        "You are a friendly, conversational voice assistant helping a person in India. "
                        "You speak and understand Telugu, Hindi, and English. Keep replies natural and concise (1-2 sentences). "
                        "If the user says ping or mentions testing tools, call the ping tool immediately."
                    )
                )
            ]
        ),
        tools=[types.Tool(function_declarations=[ping_tool])],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


async def handle_live_session(websocket: WebSocket):
    api_key = get_gemini_api_key()
    live_model = get_gemini_live_model()

    if not api_key:
        await websocket.send_json({
            "type": "error",
            "message": "GEMINI_API_KEY is not set in .env. Please set GEMINI_API_KEY in the project root .env file.",
        })
        await websocket.send_json({"type": "state", "value": "error"})
        await websocket.close()
        return

    client = genai.Client(api_key=api_key)
    config = get_live_config()

    await websocket.send_json({"type": "state", "value": "connecting"})

    try:
        async with client.aio.live.connect(model=live_model, config=config) as session:
            await websocket.send_json({"type": "state", "value": "listening"})

            async def receive_from_client():
                try:
                    while True:
                        message = await websocket.receive()
                        if "bytes" in message and message["bytes"]:
                            pcm_data = message["bytes"]
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    data=pcm_data,
                                    mime_type="audio/pcm;rate=16000",
                                )
                            )
                        elif "text" in message and message["text"]:
                            data = json.loads(message["text"])
                            msg_type = data.get("type")
                            if msg_type == "text":
                                text_val = data.get("text", "")
                                if text_val:
                                    await session.send(text=text_val, end_of_turn=True)
                            elif msg_type == "stop":
                                break
                except WebSocketDisconnect:
                    pass
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"Error receiving from client: {e}")

            async def receive_from_gemini():
                try:
                    async for response in session.receive():
                        # 1. Server content (audio, transcript, turns)
                        sc = response.server_content
                        if sc:
                            if sc.interrupted:
                                await websocket.send_json({"type": "interrupted"})
                                await websocket.send_json({"type": "state", "value": "listening"})

                            # Input transcription (user speech)
                            if sc.input_transcription and sc.input_transcription.text:
                                await websocket.send_json({
                                    "type": "transcript",
                                    "role": "user",
                                    "text": sc.input_transcription.text,
                                    "final": bool(sc.input_transcription.finished),
                                })

                            # Output transcription (assistant speech)
                            if sc.output_transcription and sc.output_transcription.text:
                                await websocket.send_json({
                                    "type": "transcript",
                                    "role": "assistant",
                                    "text": sc.output_transcription.text,
                                    "final": bool(sc.output_transcription.finished),
                                })

                            # Model audio & text parts
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
                                await websocket.send_json({"type": "state", "value": "listening"})

                        # 2. Tool calls
                        tc = response.tool_call
                        if tc and tc.function_calls:
                            await websocket.send_json({"type": "state", "value": "thinking"})
                            responses = []
                            for fc in tc.function_calls:
                                args = fc.args or {}
                                # Notify frontend of tool call
                                await websocket.send_json({
                                    "type": "tool_call",
                                    "name": fc.name,
                                    "args": args,
                                    "id": fc.id,
                                    "timestamp": time.time(),
                                })
                                # Execute dummy tool
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
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"Error receiving from Gemini: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})

            client_task = asyncio.create_task(receive_from_client())
            gemini_task = asyncio.create_task(receive_from_gemini())

            done, pending = await asyncio.wait(
                [client_task, gemini_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        print(f"Session error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.send_json({"type": "state", "value": "error"})
        except Exception:
            pass
