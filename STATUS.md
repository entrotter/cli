# CLI candidate status

## October 1 — Built-in agent execution and recorded replay

The CLI adds `agent-run` for the bounded built-in risk policy and `replay` for a
verified complete agent report. Replay derives original steps/gas budget, verifies
complete returned equality before export and never calls a model. `inspect`
displays the original decisions/reasons/provider provenance without an engine.
The optional engine stub includes this API; no runtime dependency, external
provider loader, native fallback or v0.1 report/schema change is introduced.

The missing-command regression fails before the change. Final engine-free units,
actual local Docker tests and production quality results are bound in
evidence/agent-cli/summary.json. Existing frozen model/risk samples are copied
byte-for-byte with exact provenance, not regenerated or retuned. New actual CI
pins engine c167193 and SDK b0c2ba3; package/unit jobs remain engine-free. Current
head CI, independent review and branch-protection coverage are recorded separately
in the PR/coordination checkpoint. A workflow definition is not execution evidence.

Main integration/deployment/submission remain pending. This is data-only replay
of supplied actions under matching observations, not later-block historical trace
replay, new agent advantage or full host/daemon/VM resource isolation. The original
model's unknown served snapshot/cost and nondeterminism remain disclosed.

## October 3 — bounded price replay from the CLI

`trace-observe plan.json -o observed-trace.json` now invokes the matching optional
Enginec2eb fixed-profile default worker, validates the full returned wrapper with
standalone SDKeb and compares its plan to a deep admitted snapshot before the
existing shared quota/atomic export. Recorded inspection still needs no Engine.
Regular/256KiB JSON bounds, duplicate/nesting refusal and SIGTERM/Ctrl-C cleanup
preserve existing destinations on failure/cancellation. No API/native/profile/
callback/selector option, fallback, v0.1 or agent execution change is introduced.

The old1ee parser fails the missing-command regression. Ten new unit groups
exercise matching/mutated/foreign/invalid/incomplete records, parser bounds,
package absence, signals and preserved exports; full59-unit and7-source quality
results are recorded separately. First actual-worker tests caught an incorrect
assumed validator import name that mocks/stubs had also reflected; corrected to
Engine's actual `validate_plan`. Original failed raw logs remain retained; no
weakened assertions. Real Docker observed execution/cancellation results, source
hashes, environment and exact command are captured in local/CI evidence.

The new required fixed-observation steps are inside the existing required agent
job, using a separate c2eb checkout/image. All original c167 risk/recorded replay
steps and SDKeb pins remain unchanged. CI retains both manifests and complete
new observed/failed-worker/cancellation records; no OS/Cargo/model/archive32
re-audit is claimed from these CLI checks. Current-head CI, final independent
review, protected-main/Pages and submission remain separate gates. Goal active
through the official deadline; Discord excluded.

Final local source passes 59 units (4.468s, no skips) and three actual default
Docker controls (22.499s, no skips). All seven production/script sources pass
Ruff/mypy and full Bandit with no findings; fresh advisory query covers all 42
locked identities and reports none. A fresh no-index SDK/CLI wheel installation
passes all five original inspection commands under `-I`, and the new command
refuses missing optional Engine without changing the incumbent output. All five
CLI module bytes, UTF-8 README and RECORD entries match the built wheel. The
SDK CI wheel is reused with its four module bytes/README/RECORD bound to eb9921f;
ZIP timestamps differ from a prior locally built wheel. Verification setup also
needed explicit UTF-8 metadata decoding; neither correction changed production.

Independent core review passes after fixing step-local `PYTHONPATH` for the new
image build; original required CI contexts and frozen c167 steps are preserved.
Public local evidence and scope are in [evidence/observed-run](evidence/observed-run/README.md).
Current-head CI and complete staged review remain separate from these local
results; no latest main/Pages publication claim is made here.
Final independent evidence review identified that the local strict test output
does not retain its exact admitted image ID. The current mutable build manifest
is explicitly a source reference, not launch proof. New required CI exports the
exact image manifest and launch environment; local full result facts stay scoped.

The image-provenance finding was closed with an explicit launch record (image,
plan and all imported module hashes) and a frozen 840d03 worker manifest whose
22 inputs match Engine c2eb. All three actual cases were rerun (22.459s, no skips);
new required CI retains that same launch record. The earlier mutable 43e14e
manifest had different isolated-module bytes and is not used as execution proof.


## October 3 — account replay and offline inspection

The candidate exposes `trace-position`, `position-verify` and `position-inspect`
with SDKba4/Engine88c6. Existing risk/model and price gates retain their frozen
SDK/Engine versions. Closed account/plan binding, full standalone validation,
owned execution/cancellation and quota/atomic export are required. Actual
default13 data, missing worker and admittedSIGTERM tests pass separately from
synthetic dispatch and offline tests; [evidence](evidence/position-cli/README.md)
retains exact current sources/image, full values and scoped results. No new model
call, signed strategy, profit or provider authentication is claimed. Current-head
CI, coordinator pins, human main approval and Pages remain separate.


The first c04de30 required account CI failed original-baseline verification;
its full returned artifact was not retained before proof assertions and the
cause remains unknown. Other5 CI plus frozen agent4/price3 and account missing/
cancellation cleanup passed. The test-only correction retains exact child
output before all original assertions; a synthetic focused regression confirms
failure remains strict while evidence survives. See [scoped failure evidence](evidence/position-cli/c04-failure-retention.json).
Production, images, limits, dependencies and workflows are unchanged. New-head
mandatory actual CI and full original raw review remain required.
