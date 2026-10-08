"""
Test simulating two consecutive turns across the live relay:
Turn 1: User input triggers tool call `update_profile`, tool response is sent,
        and assistant reply arrives.
Turn 2: User input (text turn) arrives, and assistant reply arrives.

Verifies:
1. Turn 1 executes tool call, pushes profile_update, and completes.
2. Turn 2 receives a reply and turn_complete (relay does not exit or freeze).
3. Session id and profile are preserved across turns.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

from fastapi.testclient import TestClient
from google.genai import types

from backend.main import app
from backend.session_store import create_session, get_session


class MockAsyncLiveSession:
    def __init__(self, responses_by_turn):
        self.responses_by_turn = responses_by_turn
        self.sent_tool_responses = []
        self.sent_client_contents = []
        self.sent_realtime_inputs = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def send_realtime_input(self, audio=None):
        self.sent_realtime_inputs.append(audio)

    async def send_client_content(self, turns=None, turn_complete=None):
        self.sent_client_contents.append((turns, turn_complete))

    async def send_tool_response(self, function_responses=None):
        self.sent_tool_responses.append(function_responses)

    async def receive(self):
        while self.responses_by_turn:
            resp = self.responses_by_turn.pop(0)
            yield resp
            sc = getattr(resp, "server_content", None)
            if sc and getattr(sc, "turn_complete", False):
                break


def make_turn_1_and_2_responses():
    # Turn 1 responses from Gemini
    # 1. User input transcript
    r1 = SimpleNamespace(
        session_resumption_update=None,
        go_away=None,
        server_content=SimpleNamespace(
            interrupted=False,
            input_transcription=SimpleNamespace(text="I have 10th pass and know tailoring", finished=True),
            output_transcription=None,
            model_turn=None,
            turn_complete=False,
        ),
        tool_call=None,
    )
    # 2. Tool call: update_profile
    fc = SimpleNamespace(
        name="update_profile",
        id="call_turn1_123",
        args={"education_level": "10th", "interests": ["tailoring"]},
    )
    r2 = SimpleNamespace(
        session_resumption_update=None,
        go_away=None,
        server_content=None,
        tool_call=SimpleNamespace(function_calls=[fc]),
    )
    # 3. Model speech & output transcription
    part = SimpleNamespace(
        inline_data=SimpleNamespace(data=b"\x00\x01" * 120),
        text=None,
    )
    r3 = SimpleNamespace(
        session_resumption_update=None,
        go_away=None,
        server_content=SimpleNamespace(
            interrupted=False,
            input_transcription=None,
            output_transcription=SimpleNamespace(text="Namaste! Tailoring is a great skill.", finished=True),
            model_turn=SimpleNamespace(parts=[part]),
            turn_complete=False,
        ),
        tool_call=None,
    )
    # 4. Turn 1 complete
    r4 = SimpleNamespace(
        session_resumption_update=None,
        go_away=None,
        server_content=SimpleNamespace(
            interrupted=False,
            input_transcription=None,
            output_transcription=None,
            model_turn=None,
            turn_complete=True,
        ),
        tool_call=None,
    )

    # Turn 2 responses from Gemini
    # 5. User input transcript for Turn 2
    r5 = SimpleNamespace(
        session_resumption_update=None,
        go_away=None,
        server_content=SimpleNamespace(
            interrupted=False,
            input_transcription=SimpleNamespace(text="Can I do tailoring from home?", finished=True),
            output_transcription=None,
            model_turn=None,
            turn_complete=False,
        ),
        tool_call=None,
    )
    # 6. Assistant output for Turn 2
    part2 = SimpleNamespace(
        inline_data=SimpleNamespace(data=b"\x02\x03" * 120),
        text=None,
    )
    r6 = SimpleNamespace(
        session_resumption_update=None,
        go_away=None,
        server_content=SimpleNamespace(
            interrupted=False,
            input_transcription=None,
            output_transcription=SimpleNamespace(
                text="Yes, self employment tailoring courses allow working from home.",
                finished=True,
            ),
            model_turn=SimpleNamespace(parts=[part2]),
            turn_complete=False,
        ),
        tool_call=None,
    )
    # 7. Turn 2 complete
    r7 = SimpleNamespace(
        session_resumption_update=None,
        go_away=None,
        server_content=SimpleNamespace(
            interrupted=False,
            input_transcription=None,
            output_transcription=None,
            model_turn=None,
            turn_complete=True,
        ),
        tool_call=None,
    )

    return [r1, r2, r3, r4, r5, r6, r7]


def test_two_consecutive_turns_with_tool_call_and_text_reply():
    mock_responses = make_turn_1_and_2_responses()
    mock_session = MockAsyncLiveSession(mock_responses)

    with patch("backend.live.get_gemini_api_key", return_value="dummy_key_for_test"), \
         patch("backend.live.get_gemini_live_model", return_value="gemini-3.8-live"), \
         patch("backend.live.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.live.connect.return_value = mock_session
        mock_client_cls.return_value = mock_client

        client = TestClient(app)
        with client.websocket_connect("/ws/live") as ws:
            # 1. Receive session_id
            init_msg = ws.receive_json()
            assert init_msg["type"] == "session_id"
            session_id = init_msg["value"]
            assert session_id is not None

            # 2. Client sends start
            ws.send_json({"type": "start", "language_hint": "te"})

            # Turn 1 events should arrive
            received_messages = []
            turn1_assistant_replied = False
            turn2_assistant_replied = False

            # Collect messages until turn 1 finishes and turn 2 is sent
            while True:
                msg = ws.receive()
                if "bytes" in msg and msg["bytes"]:
                    continue
                if "text" in msg and msg["text"]:
                    data = json.loads(msg["text"])
                    received_messages.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        if "Namaste" in data.get("text", ""):
                            turn1_assistant_replied = True
                    if data.get("type") == "turn_complete" and turn1_assistant_replied:
                        # Turn 1 finished! Now send Turn 2
                        ws.send_json({"type": "text", "text": "Can I do tailoring from home?"})
                        break

            # Turn 2 events should now arrive
            while True:
                msg = ws.receive()
                if "bytes" in msg and msg["bytes"]:
                    continue
                if "text" in msg and msg["text"]:
                    data = json.loads(msg["text"])
                    received_messages.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        if "self employment tailoring" in data.get("text", ""):
                            turn2_assistant_replied = True
                    if data.get("type") == "turn_complete" and turn2_assistant_replied:
                        # Turn 2 finished! Stop session
                        ws.send_json({"type": "stop"})
                        break

            assert turn1_assistant_replied is True, "Assistant reply did not arrive in Turn 1"
            assert turn2_assistant_replied is True, "Assistant reply did not arrive in Turn 2"

            # Check that tool response was sent for update_profile
            assert len(mock_session.sent_tool_responses) == 1
            tool_resp_list = mock_session.sent_tool_responses[0]
            assert len(tool_resp_list) == 1
            tr = tool_resp_list[0]
            assert tr.name == "update_profile"
            assert tr.id == "call_turn1_123"
            assert tr.scheduling == types.FunctionResponseScheduling.WHEN_IDLE

            # Check session profile state was updated and persisted
            stored_sess = get_session(session_id)
            assert stored_sess is not None
            assert stored_sess.profile.get("education_level") == "10th"
            assert stored_sess.profile.get("interests") == ["tailoring"]


def test_update_profile_scheduling_env_configurable():
    import os
    from backend.live import get_update_profile_scheduling

    with patch.dict(os.environ, {"LIVE_UPDATE_SCHEDULING": "SILENT"}):
        assert get_update_profile_scheduling() == types.FunctionResponseScheduling.SILENT

    with patch.dict(os.environ, {"LIVE_UPDATE_SCHEDULING": "WHEN_IDLE"}):
        assert get_update_profile_scheduling() == types.FunctionResponseScheduling.WHEN_IDLE

    # Default without env set
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LIVE_UPDATE_SCHEDULING", None)
        assert get_update_profile_scheduling() == types.FunctionResponseScheduling.WHEN_IDLE


def test_initial_greeting_loaded_from_system_instruction_file():
    from backend.live import load_initial_greeting, load_system_instruction
    greeting = load_initial_greeting()
    sys_inst = load_system_instruction()
    assert greeting != ""
    assert "[INITIAL_GREETING]" not in sys_inst
    assert "greet" in greeting.lower()
