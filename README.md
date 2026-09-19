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

`--local` additionally requires the separately installed engine. Without it,
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
paths have no aggregate retention quota; manage free disk space locally.

A bounded engine API may return 503 when connections/storage are busy or 507
when its report directory is full. The SDK reports that status and never retries
a POST automatically. Export/remove old reports locally before retrying a full
store. The CLI remains usable with the SDK alone for API calls; this change does
not add an engine runtime dependency or change the v0.1 JSON format.
