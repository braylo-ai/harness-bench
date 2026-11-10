"""Three harnesses over the same SIMULATED model.

  single   - one agent, all 8 tools, one growing context
  planner  - planner call -> one sub-agent per independent chain (parallel, small contexts,
             2 tools each) -> aggregator does join steps and answers
  handoff  - chain of specialist agents, 3 steps each, passing a handoff note forward

Token sizes below are fixed ASSUMPTIONS (prompt overheads, trace sizes).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .mock_llm import ErrorModel, Meter, MockLLM, Pricing
from .tasks import Task

SYS = 120  # system prompt tokens
SYS_SUB = 80  # sub-agent / specialist system prompt
TOOL_DESC = 60  # per tool schema
TASK_PER_STEP = 25  # task description per step
STEP_TRACE = 80  # tool call + result appended to context
ERR_TRACE = 30  # error message appended on retry
VALUE_NOTE = 15  # one value in a handoff note


class Failure(Exception):
    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


@dataclass
class Outcome:
    arch: str
    task_id: str
    family: str
    success: bool
    failure: str  # ok | format | tool_error | context_overflow | wrong_arg | handoff_loss | bad_plan
    latency_s: float
    calls: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    agents: int
    events: dict = field(default_factory=dict)


class Run:
    """Shared state for one task execution."""

    def __init__(
        self, task: Task, rng: random.Random, errors: ErrorModel, pricing: Pricing
    ) -> None:
        self.task = task
        self.rng = rng
        self.e = errors
        self.p = pricing
        self.meter = Meter()
        self.llm = MockLLM(rng, errors, pricing, self.meter)
        self.values: dict[int, int] = {}
        self.causes: list[str] = []

    def corrupt(self, sid: int, cause: str) -> None:
        self.values[sid] = (self.values[sid] + 1 + self.rng.randint(0, 997)) % 1000
        self.causes.append(cause)
        self.meter.note(cause)

    def do_step(self, sid: int, ctx: list[int]) -> float:
        """Execute one tool step inside an agent whose context size is ctx[0]. Returns latency."""
        step = self.task.steps[sid]
        lat, attempts = 0.0, 0
        while True:
            if ctx[0] > self.e.max_ctx:
                raise Failure("context_overflow")
            lat += self.llm.call(ctx[0], 40)
            kind = None
            if self.llm.roll(self.e.p_format):
                kind = "format"
            elif self.llm.roll(self.e.p_tool_transient):
                kind = "tool_error"
            if kind is None:
                break
            self.meter.note(kind + "_retry")
            ctx[0] += ERR_TRACE
            attempts += 1
            if attempts > self.e.max_retries:
                raise Failure(kind)
        self.values[sid] = self.task.run_step(step, self.values)
        if self.llm.roll(self.e.p_wrong(ctx[0])):
            self.corrupt(sid, "wrong_arg")
        ctx[0] += STEP_TRACE
        return lat

    def handoff(self, sids: list[int], needed: set[int], recover_ctx: int) -> float:
        """Pass values to another agent. Lost values that are still needed are re-asked
        (p_recover) or silently garbled. Returns extra latency from re-asks."""
        lat = 0.0
        for sid in sids:
            if not self.llm.roll(self.e.p_handoff_loss):
                continue
            self.meter.note("handoff_lost")
            if sid not in needed:
                continue
            if self.llm.roll(self.e.p_recover):
                self.meter.note("handoff_recovered")
                lat += self.llm.call(recover_ctx, 20)
            else:
                self.corrupt(sid, "handoff_loss")
        return lat

    def finish(
        self, arch: str, latency: float, agents: int, failure: str | None = None
    ) -> Outcome:
        if failure is None:
            ok = self.task.answer(self.values) == self.task.gold()
            failure = "ok" if ok else (self.causes[0] if self.causes else "unknown")
        else:
            ok = False
        m = self.meter
        return Outcome(
            arch,
            self.task.id,
            self.task.family,
            ok,
            "ok" if ok else failure,
            latency,
            m.calls,
            m.tokens_in,
            m.tokens_out,
            m.cost(self.p),
            agents,
            dict(m.events),
        )


def run_single(task: Task, rng, errors=None, pricing=None) -> Outcome:
    r = Run(task, rng, errors or ErrorModel(), pricing or Pricing())
    ctx = [SYS + 8 * TOOL_DESC + TASK_PER_STEP * len(task.steps)]
    lat = 0.0
    try:
        for s in task.steps:
            lat += r.do_step(s.id, ctx)
        lat += r.llm.call(ctx[0], 60)
    except Failure as f:
        return r.finish("single", lat, 1, f.kind)
    return r.finish("single", lat, 1)


def run_planner(task: Task, rng, errors=None, pricing=None) -> Outcome:
    r = Run(task, rng, errors or ErrorModel(), pricing or Pricing())
    e = r.e
    n = len(task.steps)
    chains, joins = task.branches()
    agents = 2 + len(chains)
    lat = r.llm.call(SYS + 8 * TOOL_DESC + TASK_PER_STEP * n, 30 * n)  # planner
    bad_plan = r.llm.roll(e.p_plan_per_step * n)
    try:
        branch_lat = []
        for chain in chains:
            ctx = [SYS_SUB + 2 * TOOL_DESC + TASK_PER_STEP * len(chain)]
            bl = sum(r.do_step(sid, ctx) for sid in chain)
            bl += r.llm.call(ctx[0], 40)  # report back
            branch_lat.append(bl)
        lat += max(branch_lat) if branch_lat else 0.0
        if bad_plan:  # planner mis-specified one sub-task: its result is wrong
            r.corrupt(r.rng.choice(chains)[-1], "bad_plan")
        consumers = task.consumers()
        needed = {
            s
            for c in chains
            for s in c
            if s in task.sinks or any(x in joins for x in consumers[s])
        }
        sent = sorted(needed)  # sub-agents report only what the aggregator needs
        lat += r.handoff(sent, needed, SYS_SUB + 2 * TOOL_DESC)
        ctx = [SYS + 2 * TOOL_DESC + TASK_PER_STEP * n + VALUE_NOTE * len(sent)]
        for sid in joins:
            lat += r.do_step(sid, ctx)
        lat += r.llm.call(ctx[0], 60)  # aggregator answer
    except Failure as f:
        return r.finish("planner", lat, agents, f.kind)
    return r.finish("planner", lat, agents)


def run_handoff(task: Task, rng, errors=None, pricing=None, group: int = 3) -> Outcome:
    r = Run(task, rng, errors or ErrorModel(), pricing or Pricing())
    n = len(task.steps)
    ids = [s.id for s in task.steps]
    groups = [ids[i : i + group] for i in range(0, n, group)]
    consumers = task.consumers()
    lat = 0.0
    carried: list[int] = []
    try:
        for gi, g in enumerate(groups):
            later = {s for gg in groups[gi:] for s in gg}
            needed = {
                s
                for s in carried
                if s in task.sinks or any(c in later for c in consumers[s])
            }
            ctx = [
                SYS_SUB + 3 * TOOL_DESC + TASK_PER_STEP * n + VALUE_NOTE * len(carried)
            ]
            if gi > 0:
                lat += r.handoff(carried, needed, ctx[0])
            for sid in g:
                lat += r.do_step(sid, ctx)
            lat += r.llm.call(
                ctx[0], 50 if gi < len(groups) - 1 else 60
            )  # handoff note / answer
            carried = carried + g
    except Failure as f:
        return r.finish("handoff", lat, len(groups), f.kind)
    return r.finish("handoff", lat, len(groups))


HARNESSES = {"single": run_single, "planner": run_planner, "handoff": run_handoff}
