"""Fixed, optional local Engine execution; recorded inspection remains SDK-only."""

from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import stat
import sys
import threading

from .main import write_report


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate historical trace plan key")
        value[key] = item
    return value


def _read_plan(path: str) -> dict:
    with os.fdopen(
        os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)), "rb"
    ) as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("Historical trace plan must be a regular file")
        raw = source.read(262145)
    if len(raw) > 262144:
        raise ValueError("Historical trace plan exceeds 256 KiB")
    try:
        return json.loads(raw, object_pairs_hook=_unique_pairs)
    except RecursionError:
        raise ValueError(
            "Historical trace plan nesting exceeds parser limits"
        ) from None


@contextmanager
def _cancel_guard():
    if os.name != "posix" or threading.current_thread() is not threading.main_thread():
        raise ValueError("Observed CLI execution requires the POSIX main thread")
    previous = signal.getsignal(signal.SIGTERM)

    def cancelled(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, cancelled)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def execute_observed(plan_path: str, output: Path) -> int:
    try:
        from entrotter_sdk import ObservedTraceResult
        from entrotter_engine.consumer_observations import (
            ObservationStopped,
            run_trace_observed,
        )
        from entrotter_engine.trace import validate_plan
    except ImportError:
        raise ValueError(
            "Matching SDK and bounded observation Engine are required; "
            "no API or native fallback"
        ) from None

    admitted = deepcopy(validate_plan(_read_plan(plan_path)))
    try:
        with _cancel_guard():
            executed = run_trace_observed(deepcopy(admitted))
            parsed = ObservedTraceResult.parse(executed)
            result = parsed.report
            if result["trace_report"]["plan"] != admitted:
                raise ValueError(
                    "Observed result differs from admitted plan; destination preserved"
                )
            write_report(result, output)
    except ObservationStopped as stop:
        print("Error: Owned consumer observation stopped", file=sys.stderr)
        return 124 if stop.code == "deadline" else 130
    except KeyboardInterrupt:
        print("Error: Owned consumer observation cancelled", file=sys.stderr)
        return 130
    print(
        json.dumps(
            {
                "artifact_id": parsed.artifact_id,
                "trace_artifact_id": parsed.trace.artifact_id,
                "output": str(output),
                "classification": result["classification"],
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0
