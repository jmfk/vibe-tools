import json
import io
import sys
import time
import threading
import pytest
from unittest.mock import MagicMock, patch
from vibe_tools.command_output import OutputManager, JSONStream, out_status, vibe_prompt

@pytest.fixture
def output_manager():
    # Save original stdout
    original_stdout = sys.stdout
    manager = OutputManager()
    # Mock start_stdin_listener to avoid thread issues in tests
    manager.start_stdin_listener = MagicMock()
    yield manager
    # Restore stdout
    sys.stdout = original_stdout
    # Ensure listener thread is stopped if it was started
    manager._stop_listener.set()

def test_json_stream_capture(output_manager):
    # Setup JSONStream
    stream = JSONStream(output_manager)
    
    # Mock manager.log to verify it's called
    with patch.object(output_manager, 'log') as mock_log:
        stream.write("hello world\n")
        mock_log.assert_called_with("hello world", level="info", source="stdout")

def test_output_manager_server_mode_logs(output_manager):
    output_manager.set_server_mode(True)
    # Mock real_stdout AFTER set_server_mode because it overwrites it
    fake_stdout = io.StringIO()
    output_manager._real_stdout = fake_stdout
    
    output_manager.log("test message", level="info", source="test-source")
    
    output = fake_stdout.getvalue().strip()
    data = json.loads(output)
    
    assert data["type"] == "log"
    assert data["level"] == "info"
    assert data["source"] == "test-source"
    assert data["message"] == "test message"
    assert "timestamp" in data

def test_output_manager_server_mode_error(output_manager):
    output_manager.set_server_mode(True)
    fake_stdout = io.StringIO()
    output_manager._real_stdout = fake_stdout
    
    output_manager.log("error message", level="error", traceback="test-traceback")
    
    output = fake_stdout.getvalue().strip()
    data = json.loads(output)
    
    assert data["type"] == "error"
    assert data["message"] == "error message"
    assert data["traceback"] == "test-traceback"

def test_out_status_server_mode(output_manager):
    output_manager.set_server_mode(True)
    fake_stdout = io.StringIO()
    output_manager._real_stdout = fake_stdout
    
    # We need to use the global output_manager for out_status
    with patch("vibe_tools.command_output.output_manager", output_manager):
        out_status("test-phase", "in_progress", progress=50, extra="data")
        
        output = fake_stdout.getvalue().strip()
        data = json.loads(output)
        
        assert data["type"] == "status"
        assert data["phase"] == "test-phase"
        assert data["status"] == "in_progress"
        assert data["progress"] == 50
        assert data["extra"] == "data"

def test_output_manager_input_protocol(output_manager):
    output_manager.set_server_mode(True)
    fake_stdout = io.StringIO()
    output_manager._real_stdout = fake_stdout
    
    # Simulate input arriving via the listener thread logic
    # instead of actually running the thread (which is hard to test)
    # We'll just push directly to the queue
    with output_manager._lock:
        output_manager._input_queue.append("user-response")
        output_manager._input_event.set()
    
    # Now call get_input
    response = output_manager.get_input("Please enter something")
    
    # Verify prompt was emitted
    output = fake_stdout.getvalue().strip()
    prompt_data = json.loads(output)
    assert prompt_data["type"] == "prompt"
    assert prompt_data["message"] == "Please enter something"
    
    # Verify response was received
    assert response == "user-response"

def test_stdin_listener_input(output_manager):
    # We'll test the _stdin_listener_loop directly instead of starting the thread
    inputs = [
        json.dumps({"type": "input", "value": "first-input"}) + "\n",
        "" # End of stream
    ]
    
    with patch("sys.stdin.readline", side_effect=inputs):
        # Directly call the loop logic
        output_manager._stdin_listener_loop()
        
        assert "first-input" in output_manager._input_queue

def test_stdin_listener_cancel(output_manager):
    # Mock sys.stdin.readline
    inputs = [
        json.dumps({"type": "cancel"}) + "\n",
        ""
    ]
    
    # We need to mock _thread.interrupt_main and agent_manager.cleanup_session
    with patch("sys.stdin.readline", side_effect=inputs), \
         patch("vibe_tools.agent.agent_manager.cleanup_session") as mock_cleanup, \
         patch("_thread.interrupt_main") as mock_interrupt:
        
        # Directly call the loop logic
        output_manager._stdin_listener_loop()
        
        mock_cleanup.assert_called_once()
        mock_interrupt.assert_called_once()
        
        code, data = output_manager.get_final_result()
        assert data["status"] == "cancelled"

def test_cli_server_mode_status_integration(output_manager, tmp_path):
    # More direct integration test of the 'vibe status --server' flow
    output_manager.set_server_mode(True)
    fake_stdout = io.StringIO()
    output_manager._real_stdout = fake_stdout
    
    # Mock output_manager in all places it might be used
    with patch("vibe_tools.cli.output_manager", output_manager), \
         patch("vibe_tools.command_output.output_manager", output_manager), \
         patch("vibe_tools.utils.output_manager", output_manager), \
         patch("vibe_tools.commands.status.output_manager", output_manager), \
         patch("vibe_tools.utils.VIBE_PROJECT_DIR", tmp_path), \
         patch("sys.stdout", output_manager._real_stdout):
        
        from vibe_tools.cli import cli
        from click.testing import CliRunner
        
        runner = CliRunner()
        # Ensure we pass --server to the global CLI
        result = runner.invoke(cli, ["--server", "status"], catch_exceptions=False)
        
        # If we are in server mode, status command should NOT echo the report
        # It should set_final_result.
        code, data = output_manager.get_final_result()
        assert "report" in data
        
        # Also check if any log messages were emitted (e.g. from utils)
        output = fake_stdout.getvalue()
        lines = []
        for l in output.splitlines():
            if l.strip():
                try:
                    lines.append(json.loads(l))
                except json.JSONDecodeError:
                    pass
        
        # The result message is emitted by atexit, which we can call manually for the test
        from vibe_tools.cli import output_manager as cli_om
        # This is a bit hacky but it tests the logic
        code, data = output_manager.get_final_result()
        output_manager.emit_server_message("result", {"code": code, "data": data})
        
        output = fake_stdout.getvalue()
        lines = [json.loads(l) for l in output.splitlines() if l.strip()]
        result_msg = [l for l in lines if l.get("type") == "result"]
        assert len(result_msg) == 1
        assert "report" in result_msg[0]["data"]
