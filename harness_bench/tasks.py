"""SYNTHETIC task suite: each task is a DAG of tool steps with a computable gold answer.

Families
  simple - 2-step chain
  deep   - 8-step chain (every step needs the previous result)
  wide   - 8 independent lookups, answer = combination of all
  mixed  - two independent 3-step chains joined by a final step
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

TOOLS = {
    "lookup": lambda x: (x * 7919 + 13) % 1000,
    "square": lambda x: (x * x) % 997,
    "shift": lambda x: (x + 101) % 1000,
    "mix": lambda x: (x * 31 + 7) % 991,
    "fold": lambda x: (x // 3 + 211) % 1000,
    "hash": lambda x: (x * 2654435761) % 983,
    "clip": lambda x: min(x, 900) % 1000,
    "flip": lambda x: (999 - x) % 1000,
}
TOOL_NAMES = list(TOOLS)
FAMILIES = ("simple", "deep", "wide", "mixed")


@dataclass
class Step:
    id: int
    tool: str
    arg: int
    deps: list[int] = field(default_factory=list)


@dataclass
class Task:
    id: str
    family: str
    steps: list[Step]
    sinks: list[int]  # steps whose values form the answer

    def run_step(self, step: Step, values: dict[int, int]) -> int:
        return TOOLS[step.tool](step.arg + sum(values[d] for d in step.deps))

    def gold(self) -> int:
        values: dict[int, int] = {}
        for s in self.steps:
            values[s.id] = self.run_step(s, values)
        return self.answer(values)

    def answer(self, values: dict[int, int]) -> int:
        return sum(values[i] for i in self.sinks) % 1000

    def branches(self) -> tuple[list[list[int]], list[int]]:
        """Independent chains (for sub-agents) and join steps (need >1 branch)."""
        branch_of: dict[int, int] = {}
        chains: list[list[int]] = []
        joins: list[int] = []
        for s in self.steps:
            parents = {branch_of[d] for d in s.deps if d in branch_of}
            if any(d not in branch_of for d in s.deps) or len(parents) > 1:
                joins.append(s.id)
            elif parents:
                b = parents.pop()
                branch_of[s.id] = b
                chains[b].append(s.id)
            else:
                branch_of[s.id] = len(chains)
                chains.append([s.id])
        return chains, joins

    def consumers(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {s.id: [] for s in self.steps}
        for s in self.steps:
            for d in s.deps:
                out[d].append(s.id)
        return out


def make_task(family: str, rng: random.Random, idx: int = 0) -> Task:
    def st(i, deps=()):
        return Step(i, rng.choice(TOOL_NAMES), rng.randint(0, 999), list(deps))

    if family == "simple":
        steps = [st(0), st(1, [0])]
        sinks = [1]
    elif family == "deep":
        steps = [st(0)] + [st(i, [i - 1]) for i in range(1, 8)]
        sinks = [7]
    elif family == "wide":
        steps = [st(i) for i in range(8)]
        sinks = list(range(8))
    elif family == "mixed":
        steps = [
            st(0),
            st(1, [0]),
            st(2, [1]),
            st(3),
            st(4, [3]),
            st(5, [4]),
            st(6, [2, 5]),
        ]
        sinks = [6]
    else:
        raise ValueError(family)
    return Task(f"{family}-{idx}", family, steps, sinks)


def suite(n_per_family: int, seed: int = 0) -> list[Task]:
    rng = random.Random(seed)
    return [make_task(f, rng, i) for f in FAMILIES for i in range(n_per_family)]
