import os
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from backend.live import handle_live_session, GEMINI_LIVE_MODEL, GEMINI_API_KEY

load_dotenv()

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
    has_key = bool(GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_REAL_KEY")
    return {
        "status": "ok",
        "phase": 0,
        "model": GEMINI_LIVE_MODEL,
        "has_api_key": has_key,
    }

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    await handle_live_session(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
