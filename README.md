# Entrotter CLI

[Workspace setup](https://github.com/entrotter/entrotter#quick-start-without-dependencies-or-an-api-key) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT license](LICENSE)

A small Python 3.11+ interface for scenario execution and result inspection.

Install the sibling `sdk-python` source before this package. Neither is
published to PyPI. From a workspace with both repositories:

```bash
export PYTHONPATH="$PWD/cli/src:$PWD/sdk-python/src:$PWD/engine/src"
python3 -m entrotter_cli doctor
python3 -m entrotter_cli run scenarios/fixtures/liquidity-shock.json --local -o report.json
python3 -m entrotter_cli verify report.json
python3 -m entrotter_cli inspect report.json
```

From this repository, run unit tests with:

```bash
PYTHONPATH=src:../sdk-python/src python3 -m unittest discover -s tests -v
```

`--local` additionally requires the matching separately installed engine with
`run_native` and the bounded default runner. Configure its local Docker worker
image/socket before execution; normal local runs do not fall back if Docker is
unavailable. Follow that engine checkout's worker setup instructions. Without it,
`run` calls the API at http://127.0.0.1:8787 (override with `--api`). The optional
bearer token comes from ENTROTTER_API_TOKEN, never from command-line arguments.
`doctor` reports only whether credentials exist, never their values.

No command submits a transaction to a live chain. The CLI does not require
or accept a real wallet private key. Monetary results describe a model and
are not a trading recommendation.

Report exports are limited to 8 MiB of serialized file contents. The CLI writes
an exclusively created private temporary file and atomically replaces the chosen
destination only after a successful write. An oversized report or write failure
leaves the previous destination intact; no partial report is published. Existing
symlinks at the destination are replaced, not followed. Exports across different
paths share the export budget described below.

A bounded engine API may return 503 when connections/storage are busy or 507
when its report directory is full. The SDK reports that status and never retries
a POST automatically. Export/remove old reports locally before retrying a full
store. The CLI remains usable with the SDK alone for API calls; this change does
not add an engine runtime dependency or change the v0.1 JSON format.

## Quality checks and local package provenance

Ruff lint/format and normal mypy (including unannotated function bodies) check
`src/` and `scripts/`; Ruff also checks `typings/`. The optional engine stub defines
the v0.1 `run(dict) -> dict` and explicit `run_native(dict) -> dict` boundaries. It is not an engine implementation or
an engine installation requirement. Real engine compatibility is verified by the
separate CLI→SDK→engine workspace integration, including actual Anvil execution.

The CLI still declares `entrotter-sdk==0.1.0`, but neither package is published.
Both unit and quality workflows check out the exact SDK commit recorded in
[quality-inputs.json](quality-inputs.json). Quality CI builds that local source
with the pinned build tool and installs only that wheel using `--no-index --no-deps`.
It never resolves an unrelated registry package. To reproduce from this checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple -r requirements-quality.txt
mkdir -p _deps
git clone https://github.com/entrotter/sdk-python.git _deps/sdk
git -C _deps/sdk checkout --detach b0c2ba3bba411e548af44101ae06e879bd7b5dc0
.venv/bin/python -m build --no-isolation --wheel --outdir .quality/sdk-wheels _deps/sdk
.venv/bin/python -m pip install --no-index --no-deps .quality/sdk-wheels/*.whl
.venv/bin/python -m pip check
.venv/bin/python -m ruff check src scripts typings
.venv/bin/python -m ruff format --check src scripts typings
.venv/bin/python -m mypy src scripts
mkdir -p .quality
.venv/bin/python -m bandit --ignore-nosec -r src scripts -f json -o .quality/bandit.json
.venv/bin/python scripts/check_security.py
.venv/bin/python scripts/check_dependency_manifest.py --sdk-commit "$(git -C _deps/sdk rev-parse HEAD)"
.venv/bin/python -m pip_audit --strict --require-hashes --disable-pip -r requirements-quality.txt --progress-spinner off -f json -o .quality/dependencies.json
.venv/bin/python -m build --no-isolation --wheel --outdir .quality/wheels
```

All 42 tool/build packages are version/hash locked and audited with no ignored
advisories. The local SDK is source-checked separately, not claimed to have a
registry advisory identity; its runtime and optional dependencies must be empty,
and its build dependencies must be covered by the same audited lock. Unknown,
unpinned or changed dependencies fail. Update the lock with pinned `pip-compile`
when changing `requirements-quality.in`, then rerun the full CI suite.

Bandit runs every default rule with `--ignore-nosec`; any finding fails. The
complete scan is retained, and an additional check rejects empty/partial scans
and skipped rules. This does not prove security of native tools or the OS. Normal
mypy checks and the optional engine stub do not fully type arbitrary JSON.

The package smoke check installs CLI/SDK wheels into a fresh venv without an
engine or registry access, then runs doctor, verify and inspect on the committed
synthetic report. Its provenance is recorded in `quality-inputs.json`. The report
is a test fixture, not historical performance. Actions use immutable commits;
quality reports and unpublished MIT wheels remain available as CI artifacts.

## Explicit native development mode

Normal `run --local` uses the matching engine's bounded default. To reproduce a
trusted synthetic example without Docker, opt out explicitly:

```bash
python3 -m entrotter_cli run scenarios/fixtures/liquidity-shock.json --local --native -o report.json
```

`--native` has no whole-process CPU/RSS sandbox and is accepted only with
`--local`. A client cannot change an API server's operator-selected execution mode.
An older engine without the explicit native primitive is rejected instead of
silently using its former native default. Doctor reports Docker availability and
whether an image is configured, not daemon readiness or image verification.
Scenario/report inputs must be regular files; reads remain size-bounded and
FIFOs/devices are rejected without waiting for a writer. Output retention uses the shared budget below. Aggregate host process admission
remains an open resource-budget requirement.

## Shared report export budget

Standalone and engine CLI exports share a private POSIX bookkeeping directory:
`~/.local/state/entrotter/export-budget-v1`. Operators may set
`ENTROTTER_EXPORT_STATE_DIR` to one other private directory; all cooperating
clients must use that same directory. Requested `--output` paths keep their
existing meaning. No engine/SDK runtime dependency is added by this mechanism.

The budget is 128 MiB of tracked file contents and 128 files across output paths,
including reserved/incomplete writes. Each report remains at most 8 MiB. Admission
uses a nonblocking process lock. A durable reservation precedes creation of output
bytes, and replacement reserves the old file plus the new temporary file. A full
or busy budget rejects the write without replacing its prior destination. An
identical complete tracked export is idempotent, including at capacity.

```bash
python3 -m entrotter_cli exports
```

The command shows charged paths, pending temporary files and current usage.
Remove unwanted reports or listed abandoned temporary files locally; subsequent
admission reconciles missing files. Completed reports are never auto-deleted.
Do not delete/reset the ledger to free space: that discards tracking of existing
outputs. Invalid, inaccessible or insecure bookkeeping fails closed.

A process killed before rename can leave a temporary file, whose full reserved
size remains charged. After rename, the reservation recognizes only an exact
size/SHA-256 match at the final path. Ambiguous state retains its charge. Ordinary
exceptions remove only the owned temporary inode. Ledger contents are limited
to 256 KiB, with at most one additional 256-KiB staging file and an empty lock.

These are application file-content bounds for matching writers using one state
root. They do not constrain pre-existing untracked files, operator moves/renames,
noncooperating programs, older clients, separate state roots, filesystem metadata,
image/VM storage or all host processes. State is private to the local operator;
paths/report contents are not uploaded. POSIX locking is required even for API-only
CLI exports. The engine API's dedicated report store retains its separate quota.
A run can complete before an export is refused; do not blindly retry an API POST.

The stdlib-only `export_budget.py` is deliberately vendored identically in the
independent engine and CLI packages. Cross-repository CI requires byte equality
and verifies shared admission using both real CLIs and separate mixed processes.
Any protocol change must preserve this shared-state contract or use a deliberately
migrated protocol version; never silently reset existing reservations.
