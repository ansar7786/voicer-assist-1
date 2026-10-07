# SIH26097 — Live Voice Livelihood Pathway Engine

Deterministic rule-based livelihood & skilling pathway advisor with Gemini Live conversational voice guidance for PM-AJAY GIA.

## Architecture

- **Voice Layer:** Gemini Live bidirectional WebSocket (`/ws/live`) with PCM16 16 kHz input and PCM16 24 kHz output.
- **Rule Engine:** Pure Python deterministic rule-based engine (to be implemented in Phase 2) with SQLite database.
- **Frontend:** React + Vite single page application with routes `/consent`, `/live`, and `/official`.
- **Privacy:** Zero collection or persistence of caste, religion, community, exact address, or personal ID numbers.

## Setup Instructions

### 1. Environment Configuration

Copy `.env.example` to `.env` in the repository root:
```bash
cp .env.example .env
```

Ensure `.env` contains:
```env
GEMINI_API_KEY=<your_gemini_api_key>
GEMINI_LIVE_MODEL=gemini-3.8-live
GEMINI_TEXT_MODEL=gemini-2.5-flash
APP_ENV=dev
```

### 2. Backend Setup

```bash
# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Initialize and seed SQLite database
python -m backend.seed

# Run FastAPI backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173/` or `http://localhost:5173/live`.

## Phase Status

- **Phase 0 (Live Voice Gate):** PASSED. Multilingual Gemini Live connection, bi-directional audio relay, transcription, and `ping` tool.
- **Phase 1 (Skeleton):** PASSED. Repository structure, SQLite database, seed CSVs, React Router routes, universal footer.
