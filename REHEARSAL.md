# Demo Day Rehearsal Checklist & Script Guide (SIH26097)

## 1. Pre-Flight Checklist (15 Minutes Before Demo)

- [ ] **Hardware & Audio:**
  - Headphones connected and tested (mandatory to prevent audio echo loop back into the microphone).
  - Microphone input verified in Chrome permissions.
- [ ] **Connectivity & Fallbacks:**
  - Primary Wi-Fi connected and stable.
  - Mobile phone 5G/4G hotspot active and paired as rapid backup.
- [ ] **Environment & Credentials:**
  - `.env` configured with valid `GEMINI_API_KEY` and models (`GEMINI_LIVE_MODEL`, `GEMINI_TEXT_MODEL`).
  - Database initialized and seeded: `python -m backend.seed`.
- [ ] **Service Health:**
  - Backend running: `uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
  - Frontend running: `npm run dev` at `http://localhost:5173/`.
  - Health check verification: `curl http://127.0.0.1:8000/api/health` returns `status: "ok"`, `phase: 7`.

---

## 2. Rehearsal Script: Persona A (Livelihood & Self-Employment)

**Profile Target:**
- Education: 10th pass
- Skills / Interests: Tailoring & garment making
- Mobility: Home-only (cannot travel outside village/block)
- Available Asset: Sewing machine
- Max Duration: 3 months
- Block: Anandapuram

**Dialogue Flow:**
1. **Consent Screen:**
   - Open `/consent`. Point out clear bilingual privacy terms: *"No caste, religion, or personal ID numbers are recorded or stored."*
   - Click "Proceed to Voice Guidance".
2. **Opening & Profile Building:**
   - Assistant greets.
   - User states in Telugu or English: *"I passed 10th class, I live in Anandapuram, and I have a sewing machine at home. I want to do tailoring work."*
   - **Observer check:** Stated chips turn green (`10th`, `tailoring`, `sewing machine`, `Anandapuram`).
3. **Confirmation & Recommendations:**
   - Assistant confirms profile facts. User confirms: *"Yes, that is correct."*
   - Recommendations appear: Self-Employment Tailoring Pathway (PM-AJAY GIA grant + training).
4. **What-If Constraint Testing:**
   - User tests constraint: *"What if I can only train for 1 month?"* (or adjust What-If slider to 1 month).
   - Diff banner animates: Shows dropped longer courses and retained fast-track self-employment options.
   - Click "Why this?" / Factor Badges to inspect deterministic NSQF and PM-AJAY rules.

---

## 3. Rehearsal Script: Persona B (Hospitality / Wage Employment)

**Profile Target:**
- Education: 8th pass
- Skills / Interests: Cooking / catering assistant
- Mobility: Within block / district
- Preference: Wage employment
- Block: Bheemunipatnam

**Dialogue Flow:**
1. User connects and states: *"I have studied up to 8th standard in Bheemunipatnam. I know cooking and want a job in catering."*
2. Assistant updates profile and confirms.
3. System outputs verified PM-AJAY linked wage training courses in food production/catering assistant.

---

## 4. Failure Contingency Protocol (Success Criterion S6: Switch < 30s)

If Gemini Live latency spikes, network disconnects, or mic fails:

| Level | Failure Condition | Immediate Action | Max Delay |
|---|---|---|---|
| **Tier 1: Audio/Mic Glitch** | Audio cuts out or background noise disrupts STT. | Type message directly in the Live session chat box. Live session handles text turns seamlessly. | < 5s |
| **Tier 2: Network / Live API Offline** | WebSocket disconnects, 429 quota, or connection dropped. | Type in the text box. The system automatically falls back to offline deterministic `POST /api/extract`. | < 10s |
| **Tier 3: Total Cloud Outage** | Internet goes down entirely. | Click **"Replay Persona A"** or **"Replay Persona B"** on the Live page. Fully scripted replay runs with clear `⚠️ Cached demo replay` banner. | < 15s |
| **Tier 4: Offline Facilitator Mode** | Direct intake needed. | Navigate to `/form` for manual intake and direct pathway generation via `/api/pathways`. | < 20s |

---

## 5. Privacy Audit Verification

Run these checks before demo recording:
1. **No audio files persisted:**
   ```bash
   find . -name "*.wav" -o -name "*.mp3" -o -name "*.pcm"
   ```
   *(Must return 0 files).*
2. **No forbidden fields in database:**
   ```sql
   sqlite3 data/app.db ".schema"
   ```
   *(Confirm no columns for caste, religion, address, aadhaar, phone).*
3. **No forbidden terms in logs:**
   Inspect terminal logs to ensure only structured `EVENT: blocked_field` tokens appear, never raw sensitive text.
