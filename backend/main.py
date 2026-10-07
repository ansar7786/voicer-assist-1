from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from backend.live import (
    handle_live_session,
    get_gemini_api_key,
    get_gemini_live_model,
    ENV_PATH,
)

# Ensure project-root .env is loaded
load_dotenv(dotenv_path=ENV_PATH)

app = FastAPI(title="SIH26097 Live Voice Assistant - Phase 0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    api_key = get_gemini_api_key()
    return {
        "status": "ok",
        "phase": 0,
        "model": get_gemini_live_model(),
        "has_api_key": bool(api_key),
    }

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    await handle_live_session(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
