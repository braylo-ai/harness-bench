"""SIMULATED small LLM with error injection. No model runs.

Every call is billed by tokens and given a latency from a simple serving model. Errors are
drawn from an explicit ErrorModel. The defaults are ASSUMPTIONS chosen to be plausible for a
small, cheap model; the sweeps in bench.py show how conclusions move when they change.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class ErrorModel:
    p_format: float = 0.03  # malformed tool call / JSON -> retry
    p_tool_transient: float = 0.03  # tool timeout / 5xx -> retry
    p_wrong_base: float = 0.01  # wrong tool argument, silently wrong value
    p_wrong_per_1k_ctx: float = (
        0.012  # extra wrong-arg probability per 1k context tokens
    )
    max_ctx: int = 6000  # context limit (tokens)
    p_handoff_loss: float = 0.08  # each value passed between agents is lost/garbled
    p_recover: float = 0.6  # receiver notices a missing value and re-asks
    p_plan_per_step: float = 0.008  # planner mis-decomposes, per step in the task
    max_retries: int = 2

    def p_wrong(self, ctx_tokens: int) -> float:
        return min(0.9, self.p_wrong_base + self.p_wrong_per_1k_ctx * ctx_tokens / 1000)


@dataclass
class Pricing:
    """Illustrative small-model price per 1M tokens (USD). Not a quote for any provider."""

    usd_per_m_in: float = 0.15
    usd_per_m_out: float = 0.60
    ttft_s: float = 0.25
    s_per_out_token: float = 0.012
    s_per_1k_in: float = 0.03


@dataclass
class Meter:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    events: dict = field(default_factory=dict)

    def cost(self, p: Pricing) -> float:
        return (
            self.tokens_in * p.usd_per_m_in / 1e6
            + self.tokens_out * p.usd_per_m_out / 1e6
        )

    def note(self, k: str) -> None:
        self.events[k] = self.events.get(k, 0) + 1


class MockLLM:
    def __init__(
        self, rng: random.Random, errors: ErrorModel, pricing: Pricing, meter: Meter
    ) -> None:
        self.rng = rng
        self.e = errors
        self.p = pricing
        self.m = meter

    def call(self, prompt_tokens: int, out_tokens: int) -> float:
        """Bill one call; return its latency in seconds."""
        self.m.calls += 1
        self.m.tokens_in += prompt_tokens
        self.m.tokens_out += out_tokens
        return (
            self.p.ttft_s
            + prompt_tokens / 1000 * self.p.s_per_1k_in
            + out_tokens * self.p.s_per_out_token
        )

    def roll(self, p: float) -> bool:
        return self.rng.random() < p
