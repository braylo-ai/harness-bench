import dataclasses
import random

import pytest

from harness_bench.bench import run_all, summarize
from harness_bench.harnesses import (
    HARNESSES,
    Failure,
    Run,
    run_handoff,
    run_planner,
    run_single,
)
from harness_bench.mock_llm import ErrorModel, Meter, Pricing
from harness_bench.tasks import FAMILIES, make_task, suite

PERFECT = ErrorModel(
    p_format=0,
    p_tool_transient=0,
    p_wrong_base=0,
    p_wrong_per_1k_ctx=0,
    p_handoff_loss=0,
    p_plan_per_step=0,
)


def task(fam, seed=0):
    return make_task(fam, random.Random(seed))


# ---- tasks ---------------------------------------------------------------------------
def test_gold_is_deterministic():
    assert task("deep").gold() == task("deep").gold()


def test_branches_by_family():
    assert task("deep").branches() == ([[0, 1, 2, 3, 4, 5, 6, 7]], [])
    chains, joins = task("wide").branches()
    assert len(chains) == 8 and joins == []
    chains, joins = task("mixed").branches()
    assert chains == [[0, 1, 2], [3, 4, 5]] and joins == [6]


def test_suite_size_and_families():
    s = suite(3)
    assert len(s) == 12 and {t.family for t in s} == set(FAMILIES)


# ---- error model ------------------------------------------------------------------------
def test_wrong_probability_grows_with_context_and_is_capped():
    e = ErrorModel()
    assert e.p_wrong(0) < e.p_wrong(5000) <= 0.9
    assert ErrorModel(p_wrong_per_1k_ctx=10).p_wrong(10_000) == 0.9


def test_meter_cost():
    m = Meter(tokens_in=1_000_000, tokens_out=1_000_000)
    assert m.cost(Pricing()) == pytest.approx(0.75)


# ---- harnesses with no errors are all correct -----------------------------------------------
@pytest.mark.parametrize("arch", list(HARNESSES))
@pytest.mark.parametrize("fam", FAMILIES)
def test_error_free_harnesses_always_succeed(arch, fam):
    o = HARNESSES[arch](task(fam, 3), random.Random(1), PERFECT, Pricing())
    assert o.success and o.failure == "ok" and o.calls > 0 and o.cost_usd > 0


def test_planner_runs_wide_branches_in_parallel():
    t = task("wide")
    single = run_single(t, random.Random(0), PERFECT)
    planner = run_planner(t, random.Random(0), PERFECT)
    assert planner.latency_s < single.latency_s
    assert planner.calls > single.calls and planner.agents == 10


def test_handoff_chain_uses_groups_of_three():
    assert run_handoff(task("deep"), random.Random(0), PERFECT).agents == 3
    assert run_handoff(task("simple"), random.Random(0), PERFECT).agents == 1


def test_single_agent_rereads_growing_context():
    t = task("wide")
    s = run_single(t, random.Random(0), PERFECT)
    p = run_planner(t, random.Random(0), PERFECT)
    assert s.tokens_in > p.tokens_in  # one context re-read on every call vs small sub-agent contexts


# ---- injected failures are attributed ---------------------------------------------------------
def test_format_errors_exhaust_retries():
    e = dataclasses.replace(PERFECT, p_format=1.0)
    o = run_single(task("simple"), random.Random(0), e)
    assert not o.success and o.failure == "format" and o.calls == e.max_retries + 1


def test_context_overflow_detected():
    e = dataclasses.replace(PERFECT, max_ctx=500)
    assert run_single(task("deep"), random.Random(0), e).failure == "context_overflow"


def test_wrong_args_propagate_to_wrong_answer():
    e = dataclasses.replace(PERFECT, p_wrong_base=1.0)
    o = run_single(task("deep"), random.Random(0), e)
    assert not o.success and o.failure == "wrong_arg"


def test_unrecovered_handoff_loss_breaks_wide_task():
    e = dataclasses.replace(PERFECT, p_handoff_loss=1.0, p_recover=0.0)
    o = run_handoff(task("wide"), random.Random(0), e)
    assert not o.success and o.failure == "handoff_loss"


def test_recovered_handoff_loss_costs_calls_not_correctness():
    e = dataclasses.replace(PERFECT, p_handoff_loss=1.0, p_recover=1.0)
    base = run_planner(task("wide"), random.Random(0), PERFECT)
    o = run_planner(task("wide"), random.Random(0), e)
    assert o.success and o.calls > base.calls and o.events["handoff_recovered"] == 8


def test_bad_plan_attributed():
    e = dataclasses.replace(PERFECT, p_plan_per_step=1.0)
    o = run_planner(task("deep"), random.Random(0), e)
    assert not o.success and o.failure == "bad_plan"


def test_failure_exception_carries_kind():
    assert Failure("tool_error").kind == "tool_error"


# ---- bench ---------------------------------------------------------------------------------------
def test_run_all_is_reproducible_and_summarizes():
    tasks = suite(2)
    a = summarize(run_all(tasks, 2, ErrorModel()))
    b = summarize(run_all(tasks, 2, ErrorModel()))
    assert a == b and a["n"] == 3 * 8 * 2 and 0 <= a["success"] <= 1
