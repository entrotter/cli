#!/usr/bin/env python3
"""Require every declared Python runtime/build dependency in the audited lock."""

import argparse
import json
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def canonicalize_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def check(project, lock_text, sdk_project=None):
    locked = {
        canonicalize_name(name): version
        for name, version in re.findall(
            r"^([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==([^\s\\]+)",
            lock_text,
            re.MULTILINE,
        )
    }
    if not locked or "--hash=sha256:" not in lock_text:
        raise ValueError("Expected a complete hashed dependency lock")
    local = {}
    if sdk_project is not None:
        sdk = sdk_project["project"]
        if (
            sdk["name"] != "entrotter-sdk"
            or sdk.get("dependencies", [])
            or sdk.get("optional-dependencies", {})
        ):
            raise ValueError(
                "Local SDK must have the expected name and no runtime dependencies"
            )
        # Its build dependencies must also be covered, not hidden behind the
        # local-package exception. The CI checkout pins its source separately.
        check(sdk_project, lock_text)
        local["entrotter-sdk"] = sdk["version"]
    optional = project["project"].get("optional-dependencies", {})
    declared = (
        project["project"].get("dependencies", []) + project["build-system"]["requires"]
    )
    declared += [item for group in optional.values() for item in group]
    for raw in declared:
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)", raw)
        if (
            not match
            or {**locked, **local}.get(canonicalize_name(match[1])) != match[2]
        ):
            raise ValueError(
                "Every runtime/build dependency must be exactly pinned in the audited lock"
            )
    return {
        "runtime": project["project"].get("dependencies", []),
        "build": project["build-system"]["requires"],
        "optional_runtime": optional,
        "audited_locked_packages": len(locked),
        "local_runtime": local,
        "local_runtime_scope": "Pinned source checked separately, not a registry advisory audit",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-checkout", type=Path, default=ROOT / "_deps/sdk")
    parser.add_argument("--sdk-commit", required=True)
    args = parser.parse_args()
    expected = json.loads((ROOT / "quality-inputs.json").read_text())
    if args.sdk_commit != expected["sdk_commit"]:
        raise ValueError("SDK source revision differs from the reviewed quality pin")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    sdk_project = tomllib.loads((args.sdk_checkout / "pyproject.toml").read_text())
    scope = check(project, (ROOT / "requirements-quality.txt").read_text(), sdk_project)
    scope["local_sdk_commit"] = args.sdk_commit
    output = ROOT / ".quality/dependency-scope.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scope, indent=2) + "\n")
    print(json.dumps(scope))


if __name__ == "__main__":
    main()
