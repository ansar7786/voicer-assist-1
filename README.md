# SIH26097 — Live Voice Livelihood Pathway Engine

Deterministic rule-based livelihood & skilling pathway advisor with Gemini Live conversational voice guidance for PM-AJAY GIA.

## Architecture

- **Voice Layer:** Gemini Live bidirectional WebSocket (`/ws/live`) with PCM16 16 kHz mono client capture via AudioWorklet and PCM16 24 kHz audio output playback.
- **Deterministic Rule Engine:** Pure Python rule engine (`backend/engine.py`) calculating eligibility, duration, mobility, asset constraints, and proximity scores from SQLite.
- **Explainability API:** `POST /api/explain` synthesizes human-understandable factor explanations strictly bound to deterministic engine reason strings.
- **Resilient Fallback Modes (Phase 7):**
  - **Typed Live Session:** Real-time text messaging within the active Live WebSocket turn loop.
  - **Offline Extraction Fallback:** `POST /api/extract` for offline or intermittent network environments, normalizing livelihood attributes deterministically without LLM dependency.
  - **Cached Demo Replay:** `GET /api/demo/replay/{persona_id}` provides turn-by-turn replayed sessions for Persona A (Tailoring, Anandapuram) and Persona B (Catering, Bheemunipatnam), marked with `⚠️ Cached demo replay`.
  - **Manual Facilitator Intake:** `/form` route directly invokes `POST /api/pathways` for assisted village-level onboarding.
- **Official Dashboard (`/official`):** Honest district-level planning dashboard with strict SQL aggregation and small-cell suppression (counts < 5 masked as "Other (suppressed)").
- **Privacy & Compliance:** Zero persistent storage of raw audio or transcripts. Deterministic blocklist filters out caste, religion, community, exact address, and personal identification numbers before ingestion or logging.

---

## Setup & Running Instructions

### 1. Environment Configuration

Copy `.env.example` to `.env` in the repository root:
```bash
cp .env.example .env
```

Ensure `.env` contains:
```env
GEMINI_API_KEY=<your_api_key>
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
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend health check: `http://127.0.0.1:8000/api/health`

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173/`.

### 4. Running Backend Tests & Verifications

```bash
# Run complete test suite (all phases)
pytest backend/tests/ -v

# Run frontend build check
cd frontend && npm run build
```

---

## Application Routes

- `/consent` — Mandatory bilingual privacy consent gate.
- `/live` — Interactive Gemini Live voice guidance, live profile cards, pathway recommendations, what-if sliders, text chat fallback, and cached demo replays.
- `/form` — Manual intake form for rural facilitators and low-connectivity environments.
- `/official` — PM-AJAY administrative demand and capacity dashboard.

---

## Phase Status Summary

- **Phase 0 (Live Voice Gate):** PASSED. Bidirectional PCM16 audio relay, speech transcripts, state indicator.
- **Phase 1 (Skeleton):** PASSED. Database schema, seed data, initial routes, universal disclaimer footer.
- **Phase 2 (Engine First):** PASSED. Deterministic rule-based engine, NSQF alignment, constraint filtering, test suites.
- **Phase 3 (Live Bridge):** PASSED. WebSocket integration, system prompt grounding, bidirectional tool call dispatch.
- **Phase 4 (Live Profile via Tools):** PASSED. Dynamic tool calling (`update_profile`, `confirm_profile`), privacy blocklist, normalizers.
- **Phase 5 (Pathways & What-If):** PASSED. `get_pathways` and `set_constraint` tools, DiffBanner, factor-based explainability.
- **Phase 6 (Official View):** PASSED. Honest SQL-computed demand aggregations, small-cell suppression, mock/consented data separation.
- **Phase 7 (Fallbacks & Polish):** PASSED. Typed mode fallback, offline `/api/extract`, cached demo replays (Persona A & B), manual intake form (`/form`), text scaling (`A / A+ / A++`), and comprehensive privacy audit.
