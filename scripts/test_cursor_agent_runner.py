"""Unit tests for scripts/cursor_agent_runner.py.

A plain module (real .py extension, no top-level cursor_sdk import), so it's
imported normally rather than via SourceFileLoader. cursor_sdk itself is
never actually installed here: every test that reaches into run_language_agent
injects a fake via sys.modules.
"""

from __future__ import annotations

import argparse
import threading
import types
import unittest
import unittest.mock
from pathlib import Path

import cursor_agent_runner as car


class TestParseDurationSeconds(unittest.TestCase):
    def test_parses_seconds_minutes_hours_and_bare_numbers(self):
        self.assertEqual(car.parse_duration_seconds("30s"), 30)
        self.assertEqual(car.parse_duration_seconds("25m"), 25 * 60)
        self.assertEqual(car.parse_duration_seconds("2h"), 2 * 3600)
        self.assertEqual(car.parse_duration_seconds("3600"), 3600)

    def test_invalid_value_raises_argument_type_error(self):
        # A CLI `type=` function: bad input must be a clean argparse usage
        # error, not a silently-substituted default.
        for bad in ("", "invalid", "1x"):
            with self.assertRaises(argparse.ArgumentTypeError):
                car.parse_duration_seconds(bad)


class TestCapOrNone(unittest.TestCase):
    def test_positive_passes_through(self):
        self.assertEqual(car.cap_or_none(50000), 50000)

    def test_zero_and_negative_disable(self):
        self.assertIsNone(car.cap_or_none(0))
        self.assertIsNone(car.cap_or_none(-1))


class TestLanguageAgentResult(unittest.TestCase):
    def test_initialization_defaults(self):
        result = car.LanguageAgentResult()
        self.assertEqual(result.input_tokens, 0)
        self.assertEqual(result.output_tokens, 0)
        self.assertEqual(result.turns, 0)
        self.assertIsNone(result.capped_reason)


class TestEnsureCursorSdk(unittest.TestCase):
    def test_exits_when_missing(self):
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": None}):
            real_import = __import__

            def fake_import(name, *args, **kwargs):
                if name == "cursor_sdk" or name.startswith("cursor_sdk."):
                    raise ImportError("nope")
                return real_import(name, *args, **kwargs)

            with unittest.mock.patch("builtins.__import__", side_effect=fake_import):
                with self.assertRaises(SystemExit) as cm:
                    car.ensure_cursor_sdk()
        self.assertEqual(cm.exception.code, 1)

    def test_ok_when_present(self):
        mock_sdk = unittest.mock.MagicMock()
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_sdk}):
            car.ensure_cursor_sdk()  # must not raise


class TestRunLanguageAgentBasics(unittest.TestCase):
    def test_dispatch_error_when_cursor_sdk_missing(self):
        with unittest.mock.patch("builtins.__import__", side_effect=ImportError):
            result = car.run_language_agent(Path("/tmp"), "prompt", label="php")
        self.assertEqual(result.input_tokens, 0)
        self.assertEqual(result.output_tokens, 0)
        self.assertIsNone(result.capped_reason)

    def test_sends_prompt_with_force_true(self):
        mock_run = unittest.mock.MagicMock()
        mock_run.status = "running"
        mock_run_result = unittest.mock.MagicMock()
        mock_run_result.status = "finished"
        mock_run_result.usage = types.SimpleNamespace(input_tokens=75, output_tokens=25)
        mock_run.events.return_value = iter([])
        mock_run.wait.return_value = mock_run_result

        mock_agent_instance = unittest.mock.MagicMock()
        mock_agent_instance.send.return_value = mock_run
        mock_cursor_sdk = unittest.mock.MagicMock()
        mock_cursor_sdk.Agent.create.return_value.__enter__.return_value = mock_agent_instance
        mock_cursor_sdk.Agent.create.return_value.__exit__.return_value = None

        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}):
            result = car.run_language_agent(Path("/tmp"), "fix it please", label="php")

        self.assertEqual(result.input_tokens, 75)
        self.assertEqual(result.output_tokens, 25)
        self.assertIsNone(result.capped_reason)
        mock_agent_instance.send.assert_called_once_with(
            "fix it please", {"local": {"force": True}})


class TestVerboseAndHeartbeat(unittest.TestCase):
    """Always consumes events(); verbose only controls logging."""

    def test_log_interaction_update_handles_known_kinds_without_raising(self):
        cases = [
            types.SimpleNamespace(type="tool-call-started", tool_call={"name": "edit"}),
            types.SimpleNamespace(type="tool-call-completed", tool_call={"name": "edit"}),
            types.SimpleNamespace(type="step-started", step_id="s1"),
            types.SimpleNamespace(type="step-completed", step_id="s1", step_duration_ms=42),
            types.SimpleNamespace(type="text-delta", text="hello"),
            types.SimpleNamespace(type="thinking-delta", text="hmm"),
            types.SimpleNamespace(type="shell-output-delta", event={"chunk": "out\n"}),
            types.SimpleNamespace(type="token-delta", tokens=3),
            types.SimpleNamespace(type="turn-ended", usage=None),
            types.SimpleNamespace(type="unknown-thing"),
        ]
        for update in cases:
            car._log_interaction_update(update)  # must not raise

    def test_heartbeat_loop_logs_until_stopped(self):
        stop = threading.Event()
        calls = []
        with unittest.mock.patch.object(car, "log", side_effect=calls.append):
            t = threading.Thread(
                target=car._heartbeat_loop, args=(stop, "php"), kwargs={"interval": 0.01},
            )
            t.start()
            stop.wait(0.05)  # let a couple of intervals elapse
            stop.set()
            t.join(timeout=1)
        self.assertGreater(len(calls), 0)
        self.assertIn("php", calls[0])

    def _fake_cursor_sdk(self, events, messages=None, *, run_status="running",
                         wait_result=None):
        """Build a fake cursor_sdk module wired to a canned event list.

        If `messages` is given and `events` is empty, wrap each message as an
        sdk_message event (run_language_agent always consumes events()).
        """
        if not events and messages is not None:
            events = [
                types.SimpleNamespace(
                    kind="sdk_message", sdk_message=m, interaction_update=None)
                for m in messages
            ]
        mock_run = unittest.mock.MagicMock()
        mock_run.status = run_status
        mock_run.usage = None
        mock_run.events.return_value = iter(events)
        mock_run.wait.return_value = (
            wait_result if wait_result is not None
            else types.SimpleNamespace(usage=None, status="finished", error=None)
        )

        mock_agent_instance = unittest.mock.MagicMock()
        mock_agent_instance.send.return_value = mock_run

        mock_cursor_sdk = unittest.mock.MagicMock()
        mock_cursor_sdk.Agent.create.return_value.__enter__.return_value = (
            mock_agent_instance)
        mock_cursor_sdk.Agent.create.return_value.__exit__.return_value = None
        mock_cursor_sdk._agent = mock_agent_instance
        mock_cursor_sdk._run = mock_run
        return mock_cursor_sdk

    def test_verbose_mode_uses_events_and_logs_interaction_updates(self):
        assistant_msg = types.SimpleNamespace(type="assistant", usage=None)
        tool_update = types.SimpleNamespace(type="tool-call-started", tool_call={"name": "edit"})
        events = [
            types.SimpleNamespace(kind="interaction_update", interaction_update=tool_update,
                                  sdk_message=None),
            types.SimpleNamespace(kind="sdk_message", sdk_message=assistant_msg,
                                  interaction_update=None),
        ]
        mock_cursor_sdk = self._fake_cursor_sdk(events)
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}), \
             unittest.mock.patch.object(car, "_log_agent_message") as log_msg, \
             unittest.mock.patch.object(car, "_log_interaction_update") as log_update, \
             unittest.mock.patch.object(car, "_heartbeat_loop") as heartbeat:
            car.run_language_agent(Path("/tmp"), "prompt", label="php", verbose=True)
        log_update.assert_called_once_with(tool_update)
        log_msg.assert_called_once_with(assistant_msg)
        heartbeat.assert_not_called()

    def test_non_verbose_mode_skips_message_logging_and_starts_heartbeat(self):
        usage_msg = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=10, output_tokens=5))
        mock_cursor_sdk = self._fake_cursor_sdk([], messages=[usage_msg])
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}), \
             unittest.mock.patch.object(car, "_log_agent_message") as log_msg, \
             unittest.mock.patch.object(car, "_log_interaction_update") as log_update, \
             unittest.mock.patch.object(car, "_heartbeat_loop") as heartbeat:
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", verbose=False)
        log_msg.assert_not_called()
        log_update.assert_not_called()
        heartbeat.assert_called_once()
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(result.turns, 1)

    def test_token_delta_trips_cap_mid_turn(self):
        """token-delta updates should cancel before a turn-end usage message."""
        deltas = [
            types.SimpleNamespace(
                kind="interaction_update",
                interaction_update=types.SimpleNamespace(type="token-delta", tokens=400),
                sdk_message=None),
            types.SimpleNamespace(
                kind="interaction_update",
                interaction_update=types.SimpleNamespace(type="token-delta", tokens=200),
                sdk_message=None),
            types.SimpleNamespace(
                kind="sdk_message",
                sdk_message=types.SimpleNamespace(
                    type="usage",
                    usage=types.SimpleNamespace(input_tokens=9999, output_tokens=9999)),
                interaction_update=None),
        ]
        mock_cursor_sdk = self._fake_cursor_sdk(deltas)
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}), \
             unittest.mock.patch.object(car, "log") as log_fn:
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", token_cap=500)
        self.assertEqual(result.capped_reason, "token_cap")
        self.assertEqual(result.output_tokens, 600)
        mock_cursor_sdk._run.cancel.assert_called_once()
        self.assertTrue(any("token cap" in str(c) for c in log_fn.call_args_list))

    def test_wall_clock_timeout_logs_to_stderr(self):
        mock_cursor_sdk = self._fake_cursor_sdk([], messages=[])

        class ImmediateTimer:
            def __init__(self, interval, function):
                self.function = function
            def start(self):
                self.function()
            def cancel(self):
                pass

        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}), \
             unittest.mock.patch.object(car.threading, "Timer", ImmediateTimer), \
             unittest.mock.patch.object(car, "log") as log_fn:
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", timeout_seconds=1)
        self.assertEqual(result.capped_reason, "wall_clock_timeout")
        self.assertTrue(any("wall-clock timeout" in str(c) for c in log_fn.call_args_list))

    def test_model_defaults_to_auto_when_unset(self):
        # SDK requires a non-empty model; default is "auto".
        import os
        mock_cursor_sdk = self._fake_cursor_sdk([], messages=[])
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}), \
             unittest.mock.patch.dict("os.environ", {}, clear=False):
            os.environ.pop("CURSOR_MODEL", None)
            car.run_language_agent(Path("/tmp"), "prompt", label="php")
        self.assertEqual(mock_cursor_sdk.Agent.create.call_args.kwargs["model"], "auto")

    def test_model_env_override_respected(self):
        mock_cursor_sdk = self._fake_cursor_sdk([], messages=[])
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}), \
             unittest.mock.patch.dict("os.environ", {"CURSOR_MODEL": "gpt-5.3-codex"}):
            car.run_language_agent(Path("/tmp"), "prompt", label="php")
        self.assertEqual(
            mock_cursor_sdk.Agent.create.call_args.kwargs["model"], "gpt-5.3-codex")

    def test_token_cap_cancels_run_and_stops_processing_further_messages(self):
        under_cap = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=5, output_tokens=5))
        over_cap = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=100, output_tokens=0))
        # Past the cap — must not be applied if cancel worked.
        after_cap = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=999, output_tokens=999))
        mock_cursor_sdk = self._fake_cursor_sdk(
            [], messages=[under_cap, over_cap, after_cap])
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}):
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", token_cap=50)
        self.assertEqual(result.capped_reason, "token_cap")
        self.assertEqual(result.input_tokens, 100)
        self.assertEqual(result.output_tokens, 0)
        mock_cursor_sdk._run.cancel.assert_called_once()

    def test_turn_cap_cancels_after_n_usage_messages(self):
        """Each usage message is one completed turn; cancel at the Nth."""
        turn1 = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=10, output_tokens=1))
        turn2 = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=20, output_tokens=2))
        turn3 = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=999, output_tokens=999))
        mock_cursor_sdk = self._fake_cursor_sdk(
            [], messages=[turn1, turn2, turn3])
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}), \
             unittest.mock.patch.object(car, "log") as log_fn:
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", turn_cap=2, token_cap=None)
        self.assertEqual(result.capped_reason, "turn_cap")
        self.assertEqual(result.turns, 2)
        self.assertEqual(result.input_tokens, 20)
        self.assertEqual(result.output_tokens, 2)
        mock_cursor_sdk._run.cancel.assert_called_once()
        self.assertTrue(any("turn cap" in str(c) for c in log_fn.call_args_list))

    def test_turn_cap_disabled_allows_many_turns(self):
        msgs = [
            types.SimpleNamespace(
                type="usage",
                usage=types.SimpleNamespace(input_tokens=i, output_tokens=0))
            for i in range(1, 6)
        ]
        mock_cursor_sdk = self._fake_cursor_sdk([], messages=msgs)
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}):
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", turn_cap=None, token_cap=None)
        self.assertIsNone(result.capped_reason)
        self.assertEqual(result.turns, 5)
        mock_cursor_sdk._run.cancel.assert_not_called()

    def test_wait_usage_does_not_overwrite_tokens_after_token_cap(self):
        """Regression: run.wait() used to clobber stream usage after a cap."""
        over_cap = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=100, output_tokens=7))
        wait_result = types.SimpleNamespace(
            usage=types.SimpleNamespace(input_tokens=1, output_tokens=1),
            status="cancelled", error=None)
        mock_cursor_sdk = self._fake_cursor_sdk(
            [], messages=[over_cap], wait_result=wait_result)
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}):
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", token_cap=50)
        self.assertEqual(result.capped_reason, "token_cap")
        self.assertEqual(result.input_tokens, 100)
        self.assertEqual(result.output_tokens, 7)

    def test_late_wall_clock_timer_does_not_override_token_cap_reason(self):
        """Regression: the wall-clock timer used to only get cancelled AFTER
        run.wait() returned, so a timer racing in during that wait could
        clobber an already-set token_cap reason with wall_clock_timeout."""
        over_cap = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=100, output_tokens=0))
        mock_cursor_sdk = self._fake_cursor_sdk([], messages=[over_cap])

        fake_timer = {}

        class FakeTimer:
            def __init__(self, interval, function):
                self.function = function
                self.cancelled = False
                fake_timer["instance"] = self

            def start(self):
                pass

            def cancel(self):
                self.cancelled = True

            def fire(self):
                # Mirrors real threading.Timer: cancel() before firing is a no-op.
                if not self.cancelled:
                    self.function()

        def wait_with_late_timer_fire():
            # Simulate the timer's callback racing in while run.wait() blocks.
            fake_timer["instance"].fire()
            return types.SimpleNamespace(usage=None, status="finished", error=None)

        mock_cursor_sdk._run.wait.side_effect = wait_with_late_timer_fire

        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}), \
             unittest.mock.patch.object(car.threading, "Timer", FakeTimer):
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", token_cap=50)

        self.assertEqual(result.capped_reason, "token_cap")
        self.assertTrue(fake_timer["instance"].cancelled)

    def test_token_cap_none_disables_check(self):
        usage_msg = types.SimpleNamespace(
            type="usage",
            usage=types.SimpleNamespace(input_tokens=10_000_000, output_tokens=0))
        mock_cursor_sdk = self._fake_cursor_sdk([], messages=[usage_msg])
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}):
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", token_cap=None)
        self.assertIsNone(result.capped_reason)
        mock_cursor_sdk._run.cancel.assert_not_called()

    def test_cancel_skipped_when_run_already_terminal(self):
        over_cap = types.SimpleNamespace(
            type="usage", usage=types.SimpleNamespace(input_tokens=100, output_tokens=0))
        mock_cursor_sdk = self._fake_cursor_sdk(
            [], messages=[over_cap], run_status="finished")
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}):
            result = car.run_language_agent(
                Path("/tmp"), "prompt", label="php", token_cap=50)
        self.assertEqual(result.capped_reason, "token_cap")
        mock_cursor_sdk._run.cancel.assert_not_called()

    def test_structured_run_error_is_logged(self):
        err = types.SimpleNamespace(message="bridge died", code="internal")
        wait_result = types.SimpleNamespace(usage=None, status="error", error=err)
        mock_cursor_sdk = self._fake_cursor_sdk([], messages=[], wait_result=wait_result)
        with unittest.mock.patch.dict("sys.modules", {"cursor_sdk": mock_cursor_sdk}), \
             unittest.mock.patch.object(car, "log") as log_fn:
            car.run_language_agent(Path("/tmp"), "prompt", label="php")
        self.assertTrue(any(
            "bridge died" in str(c) and "internal" in str(c)
            for c in log_fn.call_args_list
        ))


if __name__ == "__main__":
    unittest.main()
