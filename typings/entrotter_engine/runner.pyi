"""v0.1 optional engine boundary; real behavior is checked by workspace CI."""

def run(scenario: dict) -> dict: ...
def run_native(scenario: dict) -> dict: ...
def run_agent(
    scenario: dict,
    *,
    decision_steps: list[int],
    recording: dict | None = None,
    max_requested_gas: int = 2000000,
) -> dict: ...
