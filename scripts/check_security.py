"""Reject findings, partial scans, skipped rules and empty Bandit evidence."""

import hashlib
from importlib.metadata import version
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(report, expected_files):
    metrics = report.get("metrics", {})
    totals = metrics.get("_totals", {})
    if report.get("errors") or not totals.get("loc", 0):
        raise ValueError("Security scan failed or inspected no source")
    if totals.get("skipped_tests", 0) or report.get("results") != []:
        raise ValueError("Security findings or skipped rules require investigation")
    if set(metrics) - {"_totals"} != set(expected_files):
        raise ValueError("Security scan must cover every production source/script")


def main():
    paths = {
        p.relative_to(ROOT).as_posix(): p
        for folder in [ROOT / "src", ROOT / "scripts"]
        for p in folder.rglob("*.py")
    }
    report = json.loads((ROOT / ".quality/bandit.json").read_text())
    check(report, paths)
    scope = {
        "scanner": "bandit",
        "version": version("bandit"),
        "source_sha256": {
            name: hashlib.sha256(p.read_bytes()).hexdigest()
            for name, p in paths.items()
        },
    }
    (ROOT / ".quality/security-scope.json").write_text(
        json.dumps(scope, indent=2) + "\n"
    )
    print(f"Full security scan: {len(paths)} files, no findings or skipped rules")


if __name__ == "__main__":
    main()
