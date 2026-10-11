from dataclasses import dataclass

@dataclass(frozen=True)
class Estimate:
    fingerprint: str
    amount: float
    input_tokens: int
    cached: bool


@dataclass(frozen=True)
class AIResult:
    body: str
    amount: float
    cached: bool
