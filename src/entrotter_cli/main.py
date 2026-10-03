from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import stat
import sys
from .export_budget import ExportBudget

MAX_EXPORT_BYTES = 8 * 1024 * 1024


def parser():
    p = argparse.ArgumentParser(
        prog="entrotter", description="Rewind state. Test decisions. Inspect evidence."
    )
    p.add_argument("--version", action="version", version="Entrotter 0.1.0")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "doctor", help="Report local prerequisites, without disclosing credentials"
    )
    sub.add_parser("exports", help="Inspect shared export quota and charged paths")
    r = sub.add_parser(
        "run", help="Run a scenario locally or against a local engine API"
    )
    r.add_argument("scenario")
    r.add_argument("-o", "--output", default="report.json")
    r.add_argument(
        "--local",
        action="store_true",
        help="Import the separately installed engine; no API server needed",
    )
    r.add_argument(
        "--native",
        action="store_true",
        help="With --local only: trusted development without whole-process Docker limits",
    )
    r.add_argument("--api", default="http://127.0.0.1:8787")
    a = sub.add_parser(
        "agent-run", help="Run built-in risk decisions in the local bounded worker"
    )
    a.add_argument("scenario")
    a.add_argument("--steps", nargs="+", type=int, required=True)
    a.add_argument("--gas-budget", type=int, default=2000000)
    a.add_argument("-o", "--output", default="agent-report.json")
    a = sub.add_parser(
        "replay", help="Re-execute a recorded agent report without a model call"
    )
    a.add_argument("report")
    a.add_argument("-o", "--output", default="replayed-report.json")
    v = sub.add_parser(
        "verify", help="Check the SHA-256 artifact hash (not economic correctness)"
    )
    v.add_argument("report")
    v = sub.add_parser("inspect", help="Summarize a verified result")
    v.add_argument("report")
    for name, description in (
        ("position-inspect", "Inspect recorded Aave account impact offline"),
        ("position-verify", "Verify recorded account, price and trace evidence"),
        ("observed-inspect", "Inspect recorded price observations offline"),
        ("observed-verify", "Verify a recorded price wrapper and its nested trace"),
    ):
        sub.add_parser(name, help=description).add_argument("report")
    observed = sub.add_parser(
        "trace-observe",
        help="Replay fixed historical price views in the local bounded worker",
    )
    observed.add_argument("plan")
    observed.add_argument("-o", "--output", default="observed-trace.json")
    position = sub.add_parser(
        "trace-position", help="Compare Aave account views in the local bounded worker"
    )
    position.add_argument("plan")
    position.add_argument("-o", "--output", default="position.json")
    return p


def read_json(path: str, limit: int):
    with os.fdopen(
        os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)), "rb"
    ) as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise ValueError("Input must be a regular file")
        data = f.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Input file exceeds size limit")
    return json.loads(data)


def write_report(report: dict, path: Path):
    raw = (
        json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode()
    if len(raw) > MAX_EXPORT_BYTES:
        raise ValueError("Report export exceeds 8 MiB")
    ExportBudget().write(raw, path)


def agent_configuration(report: dict) -> tuple[dict, list[int], int]:
    """Extract data-only replay parameters; the engine validates causal bindings."""
    try:
        recording = report["agent"]
        if (
            not isinstance(recording, dict)
            or recording.get("agent_version") != "0.1.0"
            or not isinstance(recording.get("provider"), dict)
        ):
            raise ValueError()
        exchanges = recording["exchanges"]
        if not isinstance(exchanges, list) or not 1 <= len(exchanges) <= 32:
            raise ValueError()
        steps = []
        for exchange in exchanges:
            request, response = exchange["request"], exchange["response"]
            step = request["observation"]["step"]
            if (
                not isinstance(response, dict)
                or set(response) != {"request_id", "choice", "reason"}
                or type(step) is not int
                or not 0 <= step <= 31
                or response["choice"] not in {"execute", "hold"}
                or not isinstance(response["reason"], str)
                or not isinstance(request["request_id"], str)
                or response["request_id"] != request["request_id"]
            ):
                raise ValueError()
            steps.append(step)
        budget = exchanges[0]["request"]["limits"]["remaining_requested_gas"]
        if (
            type(budget) is not int
            or not 21000 <= budget <= 64000000
            or len(set(steps)) != len(steps)
        ):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError("Report needs a supported agent recording") from None
    return recording, steps, budget


def agent_summary(report: dict) -> dict:
    recording, steps, budget = agent_configuration(report)
    return {
        "agent_version": recording["agent_version"],
        "provider": recording["provider"],
        "initial_requested_gas_budget": budget,
        "decisions": [
            {**exchange["response"], "step": step}
            for step, exchange in zip(steps, recording["exchanges"])
        ],
        "scope": "Recorded choices; integrity is not proof of policy or economic correctness",
    }


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "exports":
            print(json.dumps(ExportBudget().snapshot(), indent=2))
            return 0
        if args.command == "doctor":
            print(
                json.dumps(
                    {
                        "python": sys.version.split()[0],
                        "anvil_installed": shutil.which("anvil") is not None,
                        "docker_installed": shutil.which("docker") is not None,
                        "worker_image_configured": bool(
                            os.getenv("ENTROTTER_WORKER_IMAGE")
                        ),
                        "archive_rpc_configured": bool(os.getenv("ENTROTTER_RPC_URL")),
                        "api_token_configured": bool(os.getenv("ENTROTTER_API_TOKEN")),
                    },
                    indent=2,
                )
            )
            return 0
        if args.command in {"position-inspect", "position-verify"}:
            try:
                from entrotter_sdk import load_position
            except ImportError:
                raise ValueError(
                    "Matching SDK with position support is required; "
                    "use the SDK source pinned in quality-inputs.json"
                ) from None
            position = load_position(args.report)
            prices, trace = position.prices, position.trace
            summary = {
                "artifact_id": position.artifact_id,
                "profile": position.profile,
                "account": position.account,
                "plan": position.plan,
                "integrity_verified": True,
                "trace": {
                    "artifact_id": trace.artifact_id,
                    "baseline_receipts_verified": trace.baseline_verified,
                    "transaction_count": len(trace.transactions),
                },
                "prices": {
                    "artifact_id": prices.artifact_id,
                    "classification": asdict(prices.classification),
                },
                "classification": asdict(position.classification),
                "scope": position.report["scope"],
            }
            if args.command == "position-inspect":
                summary["observations"] = [asdict(row) for row in position.observations]
                summary["price_observations"] = [
                    asdict(row) for row in prices.observations
                ]
            print(json.dumps(summary, indent=2, allow_nan=False))
            return 0
        if args.command == "trace-position":
            from .position_run import execute_position

            return execute_position(args.plan, Path(args.output))
        if args.command in {"observed-inspect", "observed-verify"}:
            try:
                from entrotter_sdk import load_observed_trace
            except ImportError:
                raise ValueError(
                    "Matching SDK with observed trace support is required; "
                    "use the SDK source pinned in quality-inputs.json"
                ) from None
            observed = load_observed_trace(args.report)
            trace = observed.trace
            summary = {
                "artifact_id": observed.artifact_id,
                "profile": observed.profile,
                "integrity_verified": True,
                "trace": {
                    "artifact_id": trace.artifact_id,
                    "baseline_receipts_verified": trace.baseline_verified,
                    "transaction_count": len(trace.transactions),
                },
                "classification": asdict(observed.classification),
                "scope": (
                    "Recorded wrapper and nested trace checks; not provider authentication. "
                    "Read-only price dependence is not signed consumer strategy, profit "
                    "or full-block/root/opcode proof. Missing or unproven differences are null."
                ),
            }
            if args.command == "observed-inspect":
                summary["observations"] = [asdict(row) for row in observed.observations]
            print(json.dumps(summary, indent=2, allow_nan=False))
            return 0
        if args.command == "trace-observe":
            from .observed_run import execute_observed

            return execute_observed(args.plan, Path(args.output))
        from entrotter_sdk import Client, RunResult

        if args.command in {"agent-run", "replay"}:
            if args.command == "replay":
                reference = RunResult.parse(
                    read_json(args.report, MAX_EXPORT_BYTES)
                ).report
                recording, steps, budget = agent_configuration(reference)
                scenario = reference["scenario"]
            else:
                reference = None
                recording, steps, budget = None, args.steps, args.gas_budget
                scenario = read_json(args.scenario, 262144)
            from entrotter_engine.runner import run_agent

            try:
                executed = run_agent(
                    scenario,
                    decision_steps=steps,
                    recording=recording,
                    max_requested_gas=budget,
                )
            except TypeError:
                raise ValueError(
                    "Matching bounded agent engine is required; no native fallback"
                ) from None
            result = RunResult.parse(executed).report
            agent_configuration(result)
            if reference is not None and result != reference:
                raise ValueError("Recorded replay diverged; destination preserved")
            path = Path(args.output)
            write_report(result, path)
            print(
                f"{result['mode']} | {result['artifact_id']} | {path} | new model calls: 0"
            )
            return 0
        if args.command == "run":
            if args.native and not args.local:
                raise ValueError(
                    "--native requires --local; API execution mode is server-owned"
                )
            scenario = read_json(args.scenario, 262144)
            if args.local:
                from entrotter_engine.runner import run, run_native

                executor = run_native if args.native else run
                result = RunResult.parse(executor(scenario)).report
            else:
                client = Client(args.api, token=os.getenv("ENTROTTER_API_TOKEN"))
                result = client.run(scenario).report
            path = Path(args.output)
            write_report(result, path)
            print(f"{result['mode']} | {result['artifact_id']} | {path}")
        else:
            report = read_json(args.report, 16 * 1024 * 1024)
            parsed = RunResult.parse(report)
            if args.command == "verify":
                print(
                    f"SHA-256 verified: {parsed.artifact_id}. Integrity is not proof of model correctness."
                )
            else:
                summary = {
                    "mode": parsed.mode,
                    "scenario": report["scenario"]["id"],
                    "baseline": report["baseline"]["metrics"],
                    "candidate": report["candidate"]["metrics"],
                    "comparison": report["comparison"],
                    "assumptions": report["assumptions"],
                }
                if "agent" in report:
                    summary["agent"] = agent_summary(report)
                print(json.dumps(summary, indent=2))
        return 0
    except ImportError:
        print(
            "Missing local package. Use the workspace bootstrap; these packages are not yet published to PyPI.",
            file=sys.stderr,
        )
        return 2
    except (ValueError, OSError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
