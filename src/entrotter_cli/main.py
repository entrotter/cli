from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

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
    r.add_argument("--api", default="http://127.0.0.1:8787")
    v = sub.add_parser(
        "verify", help="Check the SHA-256 artifact hash (not economic correctness)"
    )
    v.add_argument("report")
    v = sub.add_parser("inspect", help="Summarize a verified result")
    v.add_argument("report")
    return p


def read_json(path: str, limit: int):
    with open(path, "rb") as f:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".report-", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            print(
                json.dumps(
                    {
                        "python": sys.version.split()[0],
                        "anvil_installed": shutil.which("anvil") is not None,
                        "archive_rpc_configured": bool(os.getenv("ENTROTTER_RPC_URL")),
                        "api_token_configured": bool(os.getenv("ENTROTTER_API_TOKEN")),
                    },
                    indent=2,
                )
            )
            return 0
        from entrotter_sdk import Client, RunResult

        if args.command == "run":
            scenario = read_json(args.scenario, 262144)
            if args.local:
                from entrotter_engine.runner import run

                result = RunResult.parse(run(scenario)).report
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
                print(
                    json.dumps(
                        {
                            "mode": parsed.mode,
                            "scenario": report["scenario"]["id"],
                            "baseline": report["baseline"]["metrics"],
                            "candidate": report["candidate"]["metrics"],
                            "comparison": report["comparison"],
                            "assumptions": report["assumptions"],
                        },
                        indent=2,
                    )
                )
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
