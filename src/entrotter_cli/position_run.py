"""Fixed local account replay through optional Engine, independently checked by SDK."""

from copy import deepcopy
import json
from pathlib import Path
import sys

from .main import write_report
from .observed_run import _read_plan, _cancel_guard


def execute_position(plan_path: str, output: Path) -> int:
    try:
        from entrotter_sdk import PositionResult
        from entrotter_engine.position_observations import run_position, validate_plan
        from entrotter_engine.consumer_observations import ObservationStopped
    except ImportError:
        raise ValueError(
            "Matching SDK and bounded position Engine are required; "
            "no API or native fallback"
        ) from None

    admitted = deepcopy(validate_plan(_read_plan(plan_path)))
    try:
        with _cancel_guard():
            executed = run_position(deepcopy(admitted))
            parsed = PositionResult.parse(executed)
            result = parsed.report
            if json.dumps(
                result["plan"], sort_keys=True, allow_nan=False
            ) != json.dumps(admitted, sort_keys=True, allow_nan=False):
                raise ValueError(
                    "Position result differs from admitted plan; destination preserved"
                )
            write_report(result, output)
    except ObservationStopped as stop:
        print("Error: Owned account observation stopped", file=sys.stderr)
        return 124 if stop.code == "deadline" else 130
    except KeyboardInterrupt:
        print("Error: Owned account observation cancelled", file=sys.stderr)
        return 130
    print(
        json.dumps(
            {
                "artifact_id": parsed.artifact_id,
                "trace_artifact_id": parsed.trace.artifact_id,
                "price_artifact_id": parsed.prices.artifact_id,
                "account": parsed.account,
                "output": str(output),
                "classification": result["classification"],
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0
