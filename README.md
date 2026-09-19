# Entrotter CLI

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

`--local` additionally requires the separately installed engine. Without it,
`run` calls the API at http://127.0.0.1:8787 (override with `--api`). The optional
bearer token comes from ENTROTTER_API_TOKEN, never from command-line arguments.
`doctor` reports only whether credentials exist, never their values.

## Troubleshooting

Common failures keep the diagnostic separate from the sensitive configuration:

| Situation | Typical output / next step |
| --- | --- |
| `--local` engine package is unavailable | `Missing local engine package. Add engine/src to PYTHONPATH or omit --local to use the API.` (exit 2) |
| Local API refuses the connection or returns invalid JSON | `Error: Engine is unavailable or returned invalid JSON` (exit 1), followed by a `/health` and `--api` check. |
| API returns HTTP 401/403 | Check API authorization and `ENTROTTER_API_TOKEN`; the CLI never prints the token. |
| API returns another HTTP error | Check engine health/logs. A run POST is not retried automatically; inspect its outcome before retrying. |
| Result hash/schema/mode/envelope is unsupported | `Error: Result is missing a valid content hash or schema version`; update workspace packages together and verify compatibility with the v0.1 result schema. |

These messages describe local CLI/SDK behavior; the CLI does not diagnose an
engine's internal cause. Reproduce the guidance checks with
`PYTHONPATH=src:../sdk-python/src python3 -m unittest discover -s tests -v`.
The tests exercise the guidance without contacting a remote service or
printing a token. To see the connection message against an intentionally closed
loopback port, run
`PYTHONPATH=src:../sdk-python/src python3 -m entrotter_cli run tests/fixtures/empty-scenario.json --api http://127.0.0.1:1`.

No command submits a transaction to a live chain. The CLI does not require
or accept a real wallet private key. Monetary results describe a model and
are not a trading recommendation.
