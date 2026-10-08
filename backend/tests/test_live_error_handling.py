"""
Tests for Live Session Error Handling (FR-14, NFR-10, section 9.2).
Validates:
1. Quota error (429) emits {"type": "error", "code": "quota_exceeded", "fallback": "typed"}
2. Connection drop emits {"type": "error", "code": "connection_lost", "fallback": "retry"}
3. Tool handler exception returns a tool response and emits {"type": "error", "code": "tool_error", "fallback": "retry"}
4. No-reply watchdog timeout emits {"type": "error", "code": "no_reply", "fallback": "typed"}
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app


class MockLiveSessionWithError:
    def __init__(self, exc_to_raise=None, responses=None):
        self.exc_to_raise = exc_to_raise
        self.responses = responses or []
        self.sent_tool_responses = []
        self.sent_client_contents = []

    async def __aenter__(self):
        if self.exc_to_raise and not self.responses:
            raise self.exc_to_raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def send_realtime_input(self, audio=None):
        pass

    async def send_client_content(self, turns=None, turn_complete=None):
        self.sent_client_contents.append((turns, turn_complete))

    async def send_tool_response(self, function_responses=None):
        self.sent_tool_responses.append(function_responses)

    async def receive(self):
        for resp in self.responses:
            yield resp
        if self.exc_to_raise:
            raise self.exc_to_raise
        # Keep open indefinitely if no exception and responses exhausted
        while True:
            await asyncio.sleep(1)


def test_quota_error_emits_error_event():
    quota_exc = Exception("429 Resource has been exhausted (e.g. check quota)")
    mock_session = MockLiveSessionWithError(exc_to_raise=quota_exc)

    with patch("backend.live.get_gemini_api_key", return_value="dummy_test_key"), \
         patch("backend.live.get_gemini_live_model", return_value="gemini-3.8-live"), \
         patch("backend.live.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.live.connect.return_value = mock_session
        mock_client_cls.return_value = mock_client

        client = TestClient(app)
        with client.websocket_connect("/ws/live") as ws:
            # First message is session_id
            init_msg = ws.receive_json()
            assert init_msg["type"] == "session_id"

            # Connect triggers start
            ws.send_json({"type": "start", "language_hint": "te"})

            # Look for error event
            error_found = None
            state_error_found = False

            while True:
                try:
                    msg = ws.receive_json()
                except Exception:
                    break
                if msg.get("type") == "error":
                    error_found = msg
                elif msg.get("type") == "state" and msg.get("value") == "error":
                    state_error_found = True
                    break

            assert error_found is not None, "Error event was not emitted for quota error"
            assert error_found["code"] == "quota_exceeded"
            assert "quota" in error_found["message"].lower()
            assert error_found["fallback"] == "typed"
            assert state_error_found is True


def test_connection_drop_emits_error_event():
    conn_exc = ConnectionResetError("Connection lost to Gemini")
    mock_session = MockLiveSessionWithError(exc_to_raise=conn_exc)

    with patch("backend.live.get_gemini_api_key", return_value="dummy_test_key"), \
         patch("backend.live.get_gemini_live_model", return_value="gemini-3.8-live"), \
         patch("backend.live.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.live.connect.return_value = mock_session
        mock_client_cls.return_value = mock_client

        client = TestClient(app)
        with client.websocket_connect("/ws/live") as ws:
            init_msg = ws.receive_json()
            assert init_msg["type"] == "session_id"

            ws.send_json({"type": "start", "language_hint": "te"})

            error_found = None
            state_error_found = False

            while True:
                try:
                    msg = ws.receive_json()
                except Exception:
                    break
                if msg.get("type") == "error":
                    error_found = msg
                elif msg.get("type") == "state" and msg.get("value") == "error":
                    state_error_found = True
                    break

            assert error_found is not None, "Error event was not emitted for connection drop"
            assert error_found["code"] == "connection_lost"
            assert error_found["fallback"] == "retry"
            assert state_error_found is True


def test_tool_handler_exception_returns_response_and_emits_error():
    # Simulate a tool call from Gemini
    fc = SimpleNamespace(
        name="update_profile",
        id="call_err_123",
        args={"education_level": "10th"},
    )
    r_tool = SimpleNamespace(
        session_resumption_update=None,
        go_away=None,
        server_content=None,
        tool_call=SimpleNamespace(function_calls=[fc]),
    )

    mock_session = MockLiveSessionWithError(responses=[r_tool])

    with patch("backend.live.get_gemini_api_key", return_value="dummy_test_key"), \
         patch("backend.live.get_gemini_live_model", return_value="gemini-3.8-live"), \
         patch("backend.live.handle_update_profile", side_effect=RuntimeError("Storage crash")), \
         patch("backend.live.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.live.connect.return_value = mock_session
        mock_client_cls.return_value = mock_client

        client = TestClient(app)
        with client.websocket_connect("/ws/live") as ws:
            init_msg = ws.receive_json()
            assert init_msg["type"] == "session_id"

            ws.send_json({"type": "start", "language_hint": "te"})

            error_found = None

            # Read until tool error event arrives
            for _ in range(10):
                msg = ws.receive_json()
                if msg.get("type") == "error":
                    error_found = msg
                    break

            assert error_found is not None, "Error event was not emitted when tool failed"
            assert error_found["code"] == "tool_error"
            assert error_found["fallback"] == "retry"

            # Assert that exactly one tool response was returned to Gemini (NOT skipped!)
            assert len(mock_session.sent_tool_responses) == 1
            tool_resps = mock_session.sent_tool_responses[0]
            assert len(tool_resps) == 1
            tr = tool_resps[0]
            assert tr.name == "update_profile"
            assert tr.id == "call_err_123"
            assert tr.response.get("error") == "tool_error"
            assert tr.response.get("recoverable") is True


def test_no_reply_watchdog_timeout():
    mock_session = MockLiveSessionWithError(responses=[])

    with patch("backend.live.get_gemini_api_key", return_value="dummy_test_key"), \
         patch("backend.live.get_gemini_live_model", return_value="gemini-3.8-live"), \
         patch("backend.live.get_no_reply_timeout", return_value=0.15), \
         patch("backend.live.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.live.connect.return_value = mock_session
        mock_client_cls.return_value = mock_client

        client = TestClient(app)
        with client.websocket_connect("/ws/live") as ws:
            init_msg = ws.receive_json()
            assert init_msg["type"] == "session_id"

            ws.send_json({"type": "start", "language_hint": "te"})

            # Wait for listening state
            while True:
                m = ws.receive_json()
                if m.get("type") == "state" and m.get("value") == "listening":
                    break

            # Send a user text message to start the watchdog
            ws.send_json({"type": "text", "text": "Are you there?"})

            # Assistant will stay idle. Watchdog should fire within 0.15s + buffer
            error_found = None
            state_error_found = False

            for _ in range(10):
                try:
                    m = ws.receive_json()
                    if m.get("type") == "error":
                        error_found = m
                    elif m.get("type") == "state" and m.get("value") == "error":
                        state_error_found = True
                        break
                except Exception:
                    break

            assert error_found is not None, "no_reply watchdog error was not emitted"
            assert error_found["code"] == "no_reply"
            assert error_found["fallback"] == "typed"
            assert state_error_found is True
