# CLI default fixed-price observation execution

`trace-observe` executes a data-only historical plan through the optional matching
Engine's default bounded Docker worker. It checks the complete standalone SDK
wrapper and independent admitted plan before the existing atomic quota export.
Recorded inspection and every original v0.1/agent command remain unchanged.

The local final source passes 59 unit tests with no skips, full seven-source
Ruff/mypy/Bandit checks and three actual Docker cases: successful one-input
historical observation, rejected missing worker and SIGTERM after owned worker
admission. The one original receipt has 208144 gas and eight logs; all four
complete recorded prices are 256292441874, with difference zero. Cancellation
returns 130 and missing worker returns 1; both preserve the incumbent file and
leave no owned worker. See [summary.json](summary.json), [provenance.json](provenance.json)
and the full [observed record](observed-trace.json).

This uses SDK eb9921f, Engine c2eb54d and locally configured Docker with the
matching source-built image. The existing risk/replay CI retains its separate
c167 Engine and four original cases. Independent review found that the earlier
local output did not retain its admitted image ID separately. The final gate
records `launch.json` with image, plan and imported module hashes; its frozen
worker manifest has all 22 inputs bound to Engine c2eb. All three actual cases
were rerun to close that evidence gap. New CI retains the same launch record.
New mandatory observation steps are added
inside that same required CI job; a workflow definition is not proof it ran.
Current-head CI and full independent review are reported in the PR separately.

The pre-change 1ee parser fails the missing-command regression. First actual
tests exposed an incorrect assumed validator import also present in mocks/stubs;
the real Engine API is `validate_plan`. Failure hashes are retained. Independent
core review also found missing `PYTHONPATH` in the new CI image-build step; it was
fixed before publication. Final evidence does not suppress or reinterpret failures.

This is one-input partial historical replay and fixed read-only price dependence.
It proves neither a signed consumer strategy, profit, full block/root/opcode
reconstruction nor provider authenticity. No new 32-input CLI execution, model
call, browser/Pages check, OS/Cargo audit or performance comparison is claimed.
Host/daemon/VM startup and forced/repeated signal limits remain the operator's
scope. Once an atomic export commits, later cancellation does not roll it back.
Main approval, public-site deployment and formal submission remain separate.
