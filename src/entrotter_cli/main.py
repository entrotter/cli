from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import sys


def parser():
    p = argparse.ArgumentParser(prog="entrotter", description="Rewind state. Test decisions. Inspect evidence.")
    p.add_argument("--version", action="version", version="Entrotter 0.1.0")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Report local prerequisites, without disclosing credentials")
    r = sub.add_parser("run", help="Run a scenario locally or against a local engine API")
    r.add_argument("scenario"); r.add_argument("-o", "--output", default="report.json")
    r.add_argument("--local", action="store_true", help="Import the separately installed engine; no API server needed")
    r.add_argument("--api", default="http://127.0.0.1:8787")
    v = sub.add_parser("verify", help="Check the SHA-256 artifact hash (not economic correctness)"); v.add_argument("report")
    v = sub.add_parser("inspect", help="Summarize a verified result"); v.add_argument("report")
    return p


def read_json(path: str, limit: int):
    with open(path, "rb") as f:
        data = f.read(limit+1)
    if len(data) > limit: raise ValueError("Input file exceeds size limit")
    return json.loads(data)


def error_guidance(message: str) -> str | None:
    """Return a safe next step for common SDK/API failures."""
    if message == "Engine is unavailable or returned invalid JSON":
        return "Check the local API with `entrotter doctor` and `curl http://127.0.0.1:8787/health`; pass --api if it listens elsewhere."
    if message.startswith("Engine returned HTTP 401") or message.startswith("Engine returned HTTP 403"):
        return "Check API authorization and ENTROTTER_API_TOKEN; the token value is never shown by the CLI."
    if message.startswith("Engine returned HTTP "):
        return "Check the engine's health and logs. A run POST is not retried automatically; inspect its outcome before retrying."
    if message in {
        "Result is missing a valid content hash or schema version",
        "Unknown result mode",
        "Malformed result envelope",
    }:
        return "The engine response is incompatible with this CLI/SDK. Update the workspace packages together and check the v0.1 result schema."
    return None


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            print(json.dumps({"python": sys.version.split()[0], "anvil_installed": shutil.which("anvil") is not None,
                              "archive_rpc_configured": bool(os.getenv("ENTROTTER_RPC_URL")),
                              "api_token_configured": bool(os.getenv("ENTROTTER_API_TOKEN"))}, indent=2))
            return 0
        from entrotter_sdk import Client, RunResult, verify
        if args.command == "run":
            scenario = read_json(args.scenario, 262144)
            if args.local:
                from entrotter_engine.runner import run
                result = RunResult.parse(run(scenario)).report
            else:
                client = Client(args.api, token=os.getenv("ENTROTTER_API_TOKEN"))
                result = client.run(scenario).report
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
            print(f"{result['mode']} | {result['artifact_id']} | {path}")
        else:
            report = read_json(args.report, 16*1024*1024)
            result = RunResult.parse(report)
            if args.command == "verify":
                print(f"SHA-256 verified: {result.artifact_id}. Integrity is not proof of model correctness.")
            else:
                print(json.dumps({"mode": result.mode, "scenario": report["scenario"]["id"],
                                  "baseline": report["baseline"]["metrics"],
                                  "candidate": report["candidate"]["metrics"],
                                  "comparison": report["comparison"], "assumptions": report["assumptions"]}, indent=2))
        return 0
    except ImportError as e:
        if args.command == "run" and args.local and "entrotter_engine" in str(e):
            print("Missing local engine package. Add engine/src to PYTHONPATH or omit --local to use the API.", file=sys.stderr)
        else:
            print("Missing local SDK package. Use the workspace bootstrap; these packages are not yet published to PyPI.", file=sys.stderr)
        return 2
    except (ValueError, OSError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        hint = error_guidance(str(e))
        if hint:
            print(f"Next step: {hint}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
