"""Generic Cursor SDK agent dispatch: wall-clock timeout, best-effort token/turn
caps, and heartbeat-or-verbose event logging. Callers pass a plain prompt
string in; this module knows nothing about grammars, languages, or tags.

Environment variables:
  CURSOR_API_KEY   Required to actually dispatch; read by the cursor_sdk
                    itself, never by this module.
  CURSOR_MODEL      Model for the agent (default: "auto").
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def log(msg: str) -> None:
    """Print a human-facing progress line to stderr."""
    print(msg, file=sys.stderr)


# Best-effort: enforced at turn boundaries only (see run_language_agent).
# 10x the one measured bump (solidity v1.2.13: ~576k tokens).
DEFAULT_AGENT_TOKEN_CAP = 5_762_100

# Soft guess aligned with fix-semgrep-grammar's max-iterations default; not
# yet calibrated against measured bumps.
DEFAULT_AGENT_TURN_CAP = 20

DEFAULT_AGENT_TIMEOUT = "25m"


def parse_duration_seconds(duration_str: str) -> float:
    """argparse `type=` for a CLI duration flag: '30s' / '25m' / '2h' or bare seconds.

    Raises argparse.ArgumentTypeError on anything else, so a bad CLI value is
    a clean usage error rather than a silently-substituted default.
    """
    s = duration_str.strip()
    try:
        if s.endswith('s'):
            duration = datetime.timedelta(seconds=int(s[:-1]))
        elif s.endswith('m'):
            duration = datetime.timedelta(minutes=int(s[:-1]))
        elif s.endswith('h'):
            duration = datetime.timedelta(hours=int(s[:-1]))
        else:
            duration = datetime.timedelta(seconds=int(s))
    except (ValueError, IndexError):
        raise argparse.ArgumentTypeError(
            f"invalid duration {duration_str!r} (expected e.g. '30s', '25m', '2h')")
    return duration.total_seconds()


def cap_or_none(n: int) -> int | None:
    """CLI convention for cap flags: <= 0 means disabled."""
    return n if n > 0 else None


@dataclass
class LanguageAgentResult:
    input_tokens: int = 0
    output_tokens: int = 0
    turns: int = 0
    capped_reason: str | None = None


def _log_agent_message(msg: Any) -> None:
    """Log one SDK message to stderr; usage is handled by the caller."""
    match getattr(msg, "type", None):
        case "assistant":
            for block in getattr(getattr(msg, "message", None), "content", ()):
                text = getattr(block, "text", "")
                if text:
                    sys.stderr.write(f"[agent] {text}\n")
        case "thinking":
            sys.stderr.write(f"[agent:thinking] {msg.text}\n")
        case "tool_call":
            sys.stderr.write(f"[agent:tool] {msg.name} ({msg.status})\n")
        case "status":
            sys.stderr.write(f"[agent:status] {msg.status}: {msg.message}\n")
        case "usage":
            pass
        case kind:
            sys.stderr.write(f"[agent:{kind}] {msg}\n")


def _log_interaction_update(update: Any) -> None:
    """Log one interaction_update event (--verbose only)."""
    match getattr(update, "type", None):
        case "tool-call-started" | "tool-call-completed":
            tool_call = getattr(update, "tool_call", None) or {}
            name = tool_call.get("name") or tool_call.get("tool") or "tool"
            sys.stderr.write(f"[agent:{update.type}] {name}\n")
        case "step-started":
            sys.stderr.write(f"[agent:step-started] {update.step_id}\n")
        case "step-completed":
            sys.stderr.write(
                f"[agent:step-completed] {update.step_id} ({update.step_duration_ms}ms)\n")
        case "text-delta" | "thinking-delta":
            if update.text:
                sys.stderr.write(update.text)
        case "shell-output-delta":
            event = getattr(update, "event", None) or {}
            chunk = event.get("chunk") or event.get("data") or ""
            if chunk:
                sys.stderr.write(chunk)
        case _:
            pass


def _heartbeat_loop(stop: threading.Event, label: str, interval: float = 30.0) -> None:
    """Periodic liveness line so GHA doesn't kill a quiet step (~10m)."""
    start = time.monotonic()
    while not stop.wait(interval):
        elapsed = int(time.monotonic() - start)
        log(f"[agent] still working on {label}... ({elapsed}s elapsed)")


def ensure_cursor_sdk() -> None:
    """Fail fast if cursor-sdk is missing (only when the caller opted in)."""
    try:
        import cursor_sdk  # noqa: F401
    except ImportError:
        log("Error: cursor-sdk not installed. Install with: pip install cursor-sdk")
        sys.exit(1)


def _cancel_if_running(run: Any) -> None:
    """Cancel only while running (terminal cancel errors on SDK 1.0.23+)."""
    if getattr(run, "status", None) == "running":
        run.cancel()


def _trip_cap(result: LanguageAgentResult, run: Any, timer: threading.Timer,
             reason: str, message: str) -> None:
    """Record a cap reason (first one wins), log it, and cancel the run."""
    if result.capped_reason is None:
        result.capped_reason = reason
        log(f"[agent] cancelled: {message}")
    timer.cancel()
    _cancel_if_running(run)


def _log_run_failure(run_result: Any) -> None:
    """Log structured error from run.wait() if status is error."""
    if run_result is None or getattr(run_result, "status", None) != "error":
        return
    err = getattr(run_result, "error", None)
    message = getattr(err, "message", None) or getattr(run_result, "result", None) or "unknown"
    code = getattr(err, "code", None)
    log(f"Language agent run error: {message}" + (f" (code={code})" if code else ""))


def run_language_agent(root: Path, prompt: str, *, label: str = "agent",
                     verbose: bool = False,
                     timeout_seconds: float = 1500.0,
                     token_cap: int | None = DEFAULT_AGENT_TOKEN_CAP,
                     turn_cap: int | None = DEFAULT_AGENT_TURN_CAP) -> LanguageAgentResult:
    """Run the Cursor SDK agent on `prompt`; return token usage / cap info.

    Best-effort: the caller judges success (e.g. by re-running whatever check
    the prompt was meant to fix). `label` is only used for logging. Token/turn
    caps are best-effort and turn-boundary only — a single turn can overrun.
    verbose=True logs the full event stream; otherwise a heartbeat only.
    """
    log(f"$ cursor agent <{label}>  (in {root})")

    result = LanguageAgentResult()

    try:
        # Lazy import so tests can inject a fake via sys.modules.
        from cursor_sdk import Agent, LocalAgentOptions

        # force=True clears a leftover active local session.
        with Agent.create(
            model=os.environ.get("CURSOR_MODEL", "auto"),  # SDK requires non-empty
            local=LocalAgentOptions(cwd=root),
        ) as agent:
            run = agent.send(prompt, {"local": {"force": True}})

            def cancel_on_timeout():
                if result.capped_reason is None:
                    result.capped_reason = "wall_clock_timeout"
                    log(f"[agent] cancelled: wall-clock timeout "
                        f"({timeout_seconds:.0f}s)")
                _cancel_if_running(run)

            timer = threading.Timer(timeout_seconds, cancel_on_timeout)
            timer.daemon = True
            timer.start()

            heartbeat_stop = threading.Event()
            heartbeat = None
            if not verbose:
                heartbeat = threading.Thread(
                    target=_heartbeat_loop, args=(heartbeat_stop, label),
                    daemon=True,
                )
                heartbeat.start()

            # Token cap is best-effort at turn boundaries (usage messages).
            # streamed_tokens folds in token-delta updates so a cap trips
            # before the next usage message, when the runtime emits them.
            streamed_tokens = 0

            try:
                for item in run.events():
                    if item.kind == "interaction_update":
                        update = item.interaction_update
                        if verbose:
                            _log_interaction_update(update)
                        if (token_cap is not None
                                and getattr(update, "type", None) == "token-delta"):
                            streamed_tokens += int(getattr(update, "tokens", 0) or 0)
                            used = (result.input_tokens + result.output_tokens
                                    + streamed_tokens)
                            if used >= token_cap:
                                # Fold the in-flight estimate into reported totals.
                                result.output_tokens = (
                                    result.output_tokens + streamed_tokens)
                                _trip_cap(result, run, timer, "token_cap",
                                          f"best-effort token cap ({used} >= "
                                          f"{token_cap}; turn-boundary only)")
                                break
                        continue

                    msg = item.sdk_message
                    if msg is None:
                        continue
                    if verbose:
                        _log_agent_message(msg)
                    if getattr(msg, "type", None) == "usage" and msg.usage is not None:
                        # Prefer cumulative handle totals when the SDK has them.
                        usage = getattr(run, "usage", None) or msg.usage
                        result.input_tokens = usage.input_tokens
                        result.output_tokens = usage.output_tokens
                        streamed_tokens = 0
                        result.turns += 1
                        used = result.input_tokens + result.output_tokens
                        if token_cap is not None and used >= token_cap:
                            _trip_cap(result, run, timer, "token_cap",
                                      f"best-effort token cap ({used} >= "
                                      f"{token_cap}; turn-boundary only)")
                            break
                        if turn_cap is not None and result.turns >= turn_cap:
                            _trip_cap(result, run, timer, "turn_cap",
                                      f"turn cap ({result.turns} >= {turn_cap})")
                            break

                run_result = run.wait()
                # After a token-/turn-cap cancel, keep the stream's last usage —
                # wait() may return None/stale totals once the run is cancelled.
                if (result.capped_reason is None
                        and run_result is not None
                        and run_result.usage is not None):
                    result.input_tokens = run_result.usage.input_tokens
                    result.output_tokens = run_result.usage.output_tokens
                _log_run_failure(run_result)

            finally:
                if heartbeat is not None:
                    heartbeat_stop.set()
                    heartbeat.join(timeout=1)
                timer.cancel()

    except Exception as e:
        request_id = getattr(e, "request_id", None)
        suffix = f" (request_id={request_id})" if request_id else ""
        log(f"Language agent dispatch error: {e}{suffix}")
        log(traceback.format_exc())

    return result
