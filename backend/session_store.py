"""
In-memory session store for Phase 4.

Each live WebSocket session gets a SessionState object holding:
- profile: current field values (latest wins, idempotent)
- constraints: current constraint overrides
- field_history: list of {field, old, new, ts} for every change
- confirmed: bool – set by confirm_profile
- profile_update_callbacks: async callbacks to push profile_update to browser

Privacy rules:
- Transcripts are NEVER stored here or in the database.
- Only profile_json and edit_log rows go to the database.
"""
import asyncio
import time
import uuid
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("voicer_live")

# ---------------------------------------------------------------------------
# Valid enum values – used for validation in tools.py
# ---------------------------------------------------------------------------
VALID_EDUCATION_LEVELS = {"none", "primary", "8th", "10th", "12th", "ITI", "graduate"}
VALID_MOBILITY = {"home_only", "within_village", "within_block", "anywhere"}
VALID_WORK_PREFERENCE = {"self", "wage", "either"}
VALID_TIME_AVAILABLE = {"full_time", "part_time", "weekends"}
VALID_URGENCY = {"urgent", "moderate", "flexible"}

# Rate-limit: max update_profile calls per second (per session)
_RATE_LIMIT_CALLS = 5
_RATE_LIMIT_WINDOW = 1.0   # seconds


@dataclass
class SessionState:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    language: str = "en"

    # Live profile — all fields optional; built up incrementally
    profile: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)

    # Immutable history of every field update
    field_history: List[Dict[str, Any]] = field(default_factory=list)

    # Confirmation state
    confirmed: bool = False

    # Previous pathways (for what-if diffing)
    previous_pathways: List[Any] = field(default_factory=list)

    # Async callbacks (registered by live.py to push WS events)
    # Signature: async (event_type: str, payload: dict) -> None
    push_callbacks: List[Callable] = field(default_factory=list)

    # Rate-limiting state
    _rate_timestamps: List[float] = field(default_factory=list)

    # -----------------------------------------------------------------------
    # Rate limiting
    # -----------------------------------------------------------------------
    def is_rate_limited(self) -> bool:
        now = time.time()
        # Prune old timestamps
        self._rate_timestamps = [
            t for t in self._rate_timestamps if now - t < _RATE_LIMIT_WINDOW
        ]
        if len(self._rate_timestamps) >= _RATE_LIMIT_CALLS:
            return True
        self._rate_timestamps.append(now)
        return False

    # -----------------------------------------------------------------------
    # Profile field update  (idempotent: latest value wins)
    # -----------------------------------------------------------------------
    def update_field(
        self,
        field_name: str,
        new_value: Any,
        source: str = "voice",   # "voice" | "manual"
        confidence: str = "stated",  # "stated" | "inferred"
    ) -> Optional[Dict[str, Any]]:
        """
        Store field update. Returns a diff dict if the value actually changed,
        else None.
        """
        old_value = self.profile.get(field_name)
        if old_value == new_value:
            return None   # idempotent – no-op

        self.profile[field_name] = new_value

        # Track confidence per field
        if "_confidence" not in self.profile:
            self.profile["_confidence"] = {}
        self.profile["_confidence"][field_name] = confidence

        ts = time.time()
        entry = {
            "field": field_name,
            "old": old_value,
            "new": new_value,
            "source": source,
            "confidence": confidence,
            "ts": ts,
        }
        self.field_history.append(entry)
        logger.info(
            "EVENT: profile_field_updated | field: %s | source: %s | time: %.3f",
            field_name, source, ts,
        )
        return entry

    def set_confirmed(self):
        self.confirmed = True
        logger.info(
            "EVENT: profile_confirmed | session: %s | time: %.3f",
            self.session_id, time.time(),
        )

    # -----------------------------------------------------------------------
    # Callback helpers
    # -----------------------------------------------------------------------
    def register_push(self, callback: Callable):
        self.push_callbacks.append(callback)

    async def push(self, event_type: str, payload: Dict[str, Any]):
        for cb in self.push_callbacks:
            try:
                await cb(event_type, payload)
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # DB persistence helpers (profile + edit_log only, never transcripts)
    # -----------------------------------------------------------------------
    def to_profile_json(self) -> str:
        """Serialise profile (excluding _confidence internal key) to JSON."""
        exportable = {k: v for k, v in self.profile.items() if not k.startswith("_")}
        return json.dumps(exportable, ensure_ascii=False)

    def get_confidence(self, field_name: str) -> str:
        return self.profile.get("_confidence", {}).get(field_name, "missing")


# ---------------------------------------------------------------------------
# Global in-memory registry  (keyed by session_id)
# ---------------------------------------------------------------------------
_sessions: Dict[str, SessionState] = {}


def create_session(language: str = "en") -> SessionState:
    sess = SessionState(language=language)
    _sessions[sess.session_id] = sess
    logger.info("EVENT: session_created | id: %s | time: %.3f", sess.session_id, time.time())
    return sess


def get_session(session_id: str) -> Optional[SessionState]:
    if session_id in _sessions:
        return _sessions[session_id]

    # Rehydrate from SQLite if exists
    try:
        from backend.db import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, language, profile_json, constraints_json FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            sess = SessionState(
                session_id=row["id"],
                language=row["language"] or "en",
                profile=json.loads(row["profile_json"] or "{}"),
                constraints=json.loads(row["constraints_json"] or "{}"),
            )
            _sessions[sess.session_id] = sess
            logger.info("EVENT: session_rehydrated | id: %s | time: %.3f", sess.session_id, time.time())
            return sess
    except Exception:
        pass

    return None


def delete_session(session_id: str):
    _sessions.pop(session_id, None)
    logger.info("EVENT: session_deleted | id: %s | time: %.3f", session_id, time.time())
