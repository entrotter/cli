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
git -C _deps/sdk checkout --detach eb9921f30c1f0f3750140f66023e3b10d255cb20
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


## Agent execution and exact recorded replay

The proposed agent CLI requires the matching bounded engine API. The actual
integration job pins engine `c1671938edde03c59deef64dbb81d7c41a33406b` and SDK
`eb9921f30c1f0f3750140f66023e3b10d255cb20`; these candidates require independent
review before protected integration. Build/configure that engine's local Docker
worker first. In a workspace with these source checkouts:

```bash
export PYTHONPATH="$PWD/cli/src:$PWD/sdk-python/src:$PWD/engine/src"
python3 -m entrotter_cli agent-run engine/tests/data/local.json --steps 0 1 -o risk.json
python3 -m entrotter_cli replay risk.json -o risk-replayed.json
python3 -m entrotter_cli replay cli/tests/data/agent-recorded-local.json -o model-replayed.json
python3 -m entrotter_cli verify model-replayed.json
python3 -m entrotter_cli inspect model-replayed.json
```

`agent-run` uses only the built-in current-state risk policy. It accepts 1–32
unique candidate decision steps and an optional `--gas-budget` (default
2,000,000 requested gas; 21,000–64,000,000 allowed). It never generates a model
response. `replay` reads a verified complete agent report, derives its original
steps and initial gas budget, and sends only its recorded data to the bounded
worker. Provider metadata does not select a module, executable, model, credential
or URL. Both commands run locally; neither accepts `--native` or `--api`, and
missing/older engine or Docker prerequisites fail without native fallback.

Replay requires complete returned JSON equality with the reference before export.
Changed initial state, an invalid recording, failed worker or diverged result
leaves an existing output intact. Successful exports retain the existing private
atomic-write/shared-quota policy. The replay input is a regular file of at most
8 MiB; the scenario limit remains 256 KiB. Runtime preparation and host Python
object memory remain subject to the engine/operator's documented scope limits.

`inspect` adds decisions, reasons, request IDs and original provider provenance
when present. It still works without an installed engine or a model account.
Agent responses must contain exactly `request_id`, `choice` and `reason`;
inspection rejects additional fields, and displayed steps come from the causal
observation. Replay rejects these malformed responses before requesting execution.
The sample preserves the original model's nondeterminism, requested alias and
unknown monetary cost. Zero new model calls during replay does not mean its
original generation was free, deterministic or economically correct. These are
synthetic local EVM records, not new historical traces, holdouts or a new model
quality comparison. A fork report additionally needs the engine's operator-owned
archive configuration; no RPC URL is taken from provider metadata.

Actual Docker CLI tests run separately from engine-free unit/package checks:

```bash
PYTHONPATH=cli/src:sdk-python/src:engine/src python3 -m unittest discover -s cli/tests_agent -v
```

The tests fail if worker prerequisites are missing and do not skip the real
gate. They compare complete original risk/model reports, changed-state refusal,
recovery and missing-image rejection. Exact sample/source pins are in
[quality-inputs.json](quality-inputs.json); measured local evidence is in
[evidence/agent-cli/summary.json](evidence/agent-cli/summary.json).


## Inspect recorded price observations without an engine

The proposed SDK source is pinned to
`eb9921f30c1f0f3750140f66023e3b10d255cb20` in [quality-inputs.json](quality-inputs.json).
The separate observed-wrapper commands read the fixed Aave/WETH price observation
format; ordinary `inspect` and `verify` retain their v0.1 result behavior.
From a workspace with matching CLI and SDK sources:

```bash
export PYTHONPATH="$PWD/cli/src:$PWD/sdk-python/src"
python3 -m entrotter_cli observed-verify cli/tests/data/observed-price32.json
python3 -m entrotter_cli observed-inspect cli/tests/data/observed-price32.json
```

No engine, Docker, API server, RPC account, model call or export ledger is needed.
The commands accept only an input path. The SDK reads a regular JSON file of at
most 8 MiB, rejects duplicate keys and validates the sealed wrapper, nested trace
and recorded observation consistency before anything is printed. Invalid input
returns status 1 with a finite error; an older SDK gets a matching-source error.

Both commands print JSON with wrapper/trace IDs, the profile, receipt verification,
transaction count, exact integer classification and its unproven reasons.
`observed-inspect` additionally prints all four typed observation records: prices,
units, source/aggregator addresses, full signed feed-round fields, head/code
identities and finite errors. Python integer output preserves decimal digits
above JavaScript's safe integer range; use a lossless JSON reader for such values.

Status 0 means successful integrity/consistency inspection. An internally valid
record with missing or unproven price views still returns 0, with
`complete_price_views: false`, an explicit reason and `price_difference: null`.
It must not be interpreted as a zero difference or proof of a profitable strategy.
`integrity_verified` does not authenticate provider or deployed state.

The actual sample is copied byte-for-byte from SDK eb9921f: original native
32-of181/skip12 Ethereum replay and four recorded Aave/WETH view phases. Its price
difference is 789973126 raw units with unit 100000000. Read-only dependence is
not signed consumer strategy, profit or full-block/root/opcode proof. The six
separate controls are engine-sealed synthetic diagnostics, including missing
state and integers at 2**200; they are not new historical execution.
Local command and isolated wheel evidence is in
[evidence/observed-cli](evidence/observed-cli/README.md); new mandatory CI and
independent review remain distinct from the original recorded EVM evidence.

## Run fixed historical price observations locally

Select the matching Engine revision recorded as `observed_engine_commit` in
[quality-inputs.json](quality-inputs.json), currently
[c2eb54d](https://github.com/entrotter/engine/tree/c2eb54dc97509e7318216c01f98adade1da5bc6e).
Use the pinned SDK source above, rebuild that Engine's worker and configure your
local Unix Docker socket/image and private archive-capable `ENTROTTER_RPC_URL`.
The installed CLI remains optional to the Engine; recorded inspection needs only
SDK and CLI. This command requires a POSIX main thread, not an API server.

From the six-repository workspace:

```bash
export PYTHONPATH="$PWD/cli/src:$PWD/sdk-python/src:$PWD/engine/src"
python3 engine/scripts/build_worker.py --output worker-image.json
export ENTROTTER_WORKER_IMAGE="$(python3 -c 'import json; print(json.load(open("worker-image.json"))["image_id"])')"
# Set ENTROTTER_DOCKER_SOCKET to your local Docker Unix socket and
# ENTROTTER_RPC_URL privately to your archive-capable read-only source.
python3 -m entrotter_cli trace-observe engine/evidence/aave-consumer-price/native-006/plan.json -o observed-trace.json
python3 -m entrotter_cli observed-verify observed-trace.json
python3 -m entrotter_cli observed-inspect observed-trace.json
```

`trace-observe` validates a regular plan of at most 256 KiB, rejecting duplicate keys
and excess nesting. It uses only the installed fixed Aave/WETH observation profile;
there are no API, native, callback, contract or selector options. Missing/old
packages or unavailable workers fail explicitly without fallback. The Engine
retains its 150-second trace/180-second worker/resource/admission limits and permits
writes only to owned local nodes. The upstream source is read-only.

Before the shared quota-protected atomic export, the standalone SDK verifies the
complete wrapper/nested trace and the CLI checks its plan against an independent
admitted snapshot. Invalid, foreign or mutated results preserve the old destination
and emit no success JSON. SIGTERM/Ctrl-C reaches owned cleanup and returns 130;
ordinary worker failures return 1. An explicit Engine `ObservationStopped` deadline
returns 124; a worker failure is not inferred to have that precise cause. Cancellation
after the atomic export commits does not roll back that valid committed file.

The success JSON contains both artifact IDs, output path and the complete
classification. Exit 0 means a valid exported record, not complete price proof;
missing views retain null differences and unproven reasons. The source 32-input
plan above is partial historical replay, not a signed consumer strategy, profit,
authenticated provider or full-block/root/opcode reconstruction. Inspect the
[Engine's actual bounded replay and limits](https://github.com/entrotter/engine/tree/c2eb54dc97509e7318216c01f98adade1da5bc6e/evidence/bounded-consumer-observations).
The separate CLI CI gate executes a one-input canonical plan, rather than claiming
that 32-input execution again. Required original risk/recorded-agent checks keep
their frozen c167 Engine; the new fixed-price gate builds c2eb separately.
Current local execution, cancellation and installed-package evidence is in
[evidence/observed-run](evidence/observed-run/README.md).

## Compare historical Aave account impact

The matching standalone SDK is [ba4af51](https://github.com/entrotter/sdk-python/tree/ba4af512784119f23b6dea63fd24c7f5d1fdde44).
Read the committed record without an Engine, Docker, RPC or model call:

```bash
export PYTHONPATH="$PWD/cli/src:$PWD/sdk-python/src"
python3 -m entrotter_cli position-verify cli/tests/data/aave-account-position13.json
python3 -m entrotter_cli position-inspect cli/tests/data/aave-account-position13.json
```

Both commands print all three artifact IDs, the account/plan, receipt verification
and exact account/price classification. Inspection adds all four typed account
and price records, preserving raw integer precision, head/configuration/code
identities and finite errors. Status0 means verified internal consistency;
incomplete evidence keeps null differences and explicit reasons. Hashes do not
authenticate a provider, source execution or proxy implementation.

For a fresh local replay, select [Engine88c6](https://github.com/entrotter/engine/tree/88c6cd0d00f466ed7e870bd57c118aa50984f8b1),
build/configure its worker and private read-only archive source as in the price
setup above, then run:

```bash
export PYTHONPATH="$PWD/cli/src:$PWD/sdk-python/src:$PWD/engine/src"
python3 -m entrotter_cli trace-position engine/tests/data/aave-account-prefix.json -o position.json
python3 -m entrotter_cli position-verify position.json
python3 -m entrotter_cli position-inspect position.json
```

The closed256KiB plan contains exactly `position_version`, `account` and the
original `trace` plan. Only the fixed Aave V3 Ethereum account profile is supported.
No API/native/profile/callback/contract/selector options or automatic fallback
are offered. Engine150/180-second limits, owned nodes and read-only upstream
policy remain unchanged. The SDK independently checks the full returned record,
then the CLI compares the admitted account/plan snapshot before the existing
shared quota-protected atomic export. Invalid/foreign/mutated results, quota
refusal and cancellation preserve the incumbent output and emit no success JSON.
SIGTERM/Ctrl-C returns130; explicit observation deadline124; ordinary failure1.
Cancellation after an atomic commit does not roll back a valid committed file.

The original13-input record omits transaction12; all13 original receipts and
12 candidate receipts remain complete. Available borrowing differs81628966124
raw base units (denominator1e8), health3852169807877337 WAD units (denominator1e18).
Both health factors remain above one. These are aggregate account measurements,
not token balances, profit, a signed loan, liquidation or proof that WETH price
is the sole cause. No-debt health preserves raw uint256-max and a null normalized
difference. [Current CLI evidence and limits](evidence/position-cli/README.md)
separate offline inspection, synthetic dispatch tests and new actual Docker3.
Frozen agent and fixed-price gates retain their earlier SDK/Engine pins; the
new account gate uses separate matching checkouts. Packages remain unpublished.
