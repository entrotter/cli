"""Optional installed fixed-profile Engine boundary, verified by real worker CI."""

class ObservationStopped(BaseException):
    code: str
    def __init__(self, code: str) -> None: ...

def run_trace_observed(plan: dict) -> dict: ...
