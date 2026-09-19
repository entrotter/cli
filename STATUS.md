# Status

## CLI diagnostics update

- Added actionable, credential-safe hints for unavailable APIs, authorization
  failures, HTTP errors, and incompatible result envelopes.
- Verified: `PYTHONPATH=src:../sdk-python/src python3 -m unittest discover -s tests -v`
  — 10 tests passed.
- Reproduced API-unavailable, missing-local-engine, and invalid-result messages
  against a closed loopback port, the absent optional engine package, and the
  invalid JSON fixture respectively. No remote service or credentials used.
