"""Run the suite under every harness, then sweep the two assumptions that decide the winner.

    python -m harness_bench.bench        # writes results/bench.json + results/bench.md
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import random
import sys
from collections import Counter
from pathlib import Path

from .harnesses import HARNESSES
from .mock_llm import ErrorModel, Pricing
from .tasks import FAMILIES, suite


def pct(xs, p):
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def run_all(tasks, trials: int, errors: ErrorModel, seed: int = 0):
    out = []
    for arch, fn in HARNESSES.items():
        for t_i, t in enumerate(tasks):
            for k in range(trials):
                out.append(
                    fn(t, random.Random(f"{seed}-{t.id}-{k}"), errors, Pricing())
                )
    return out


def summarize(outs) -> dict:
    n = len(outs)
    return {
        "n": n,
        "success": round(sum(o.success for o in outs) / n, 4),
        "mean_cost_usd_per_1k_tasks": round(
            sum(o.cost_usd for o in outs) / n * 1000, 4
        ),
        "mean_tokens": round(sum(o.tokens_in + o.tokens_out for o in outs) / n, 1),
        "mean_calls": round(sum(o.calls for o in outs) / n, 2),
        "p50_latency_s": round(pct([o.latency_s for o in outs], 50), 2),
        "p95_latency_s": round(pct([o.latency_s for o in outs], 95), 2),
        "agents": round(sum(o.agents for o in outs) / n, 2),
        "failures": dict(Counter(o.failure for o in outs if not o.success)),
    }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="tasks per family")
    ap.add_argument("--trials", type=int, default=4)
    ap.add_argument("--out", default="results")
    a = ap.parse_args(argv)
    tasks = suite(a.n, seed=0)
    base = ErrorModel()
    outs = run_all(tasks, a.trials, base)
    table = {
        f"{arch}/{fam}": summarize(
            [o for o in outs if o.arch == arch and o.family == fam]
        )
        for fam in FAMILIES
        for arch in HARNESSES
    }
    overall = {
        arch: summarize([o for o in outs if o.arch == arch]) for arch in HARNESSES
    }
    sweeps = []
    sub = [t for t in tasks if t.family in ("deep", "wide")]
    for name, values in (
        ("p_wrong_per_1k_ctx", [0.0, 0.006, 0.012, 0.024, 0.048]),
        ("p_handoff_loss", [0.0, 0.04, 0.08, 0.16]),
    ):
        for v in values:
            em = dataclasses.replace(base, **{name: v})
            o2 = run_all(sub, a.trials, em, seed=1)
            for fam in ("deep", "wide"):
                sweeps.append(
                    {
                        "param": name,
                        "value": v,
                        "family": fam,
                        **{
                            arch: round(
                                sum(
                                    o.success
                                    for o in o2
                                    if o.arch == arch and o.family == fam
                                )
                                / sum(
                                    1 for o in o2 if o.arch == arch and o.family == fam
                                ),
                                4,
                            )
                            for arch in HARNESSES
                        },
                    }
                )
    res = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "note": "SIMULATED model with injected errors; prices/latencies are assumptions, not provider quotes",
        "error_model": dataclasses.asdict(base),
        "pricing": dataclasses.asdict(Pricing()),
        "tasks_per_family": a.n,
        "trials": a.trials,
        "overall": overall,
        "by_family": table,
        "sweeps": sweeps,
    }
    md = [
        "| family | harness | success | cost / 1k tasks (USD) | tokens | calls | p50 s | p95 s | agents | failures |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for k, s in table.items():
        fam, arch = k.split("/")[1], k.split("/")[0]
        fails = ", ".join(
            f"{a2} {c}" for a2, c in sorted(s["failures"].items(), key=lambda x: -x[1])
        )
        md.append(
            f"| {fam} | {arch} | {s['success']:.3f} | {s['mean_cost_usd_per_1k_tasks']:.3f} | {s['mean_tokens']:.0f} | "
            f"{s['mean_calls']:.1f} | {s['p50_latency_s']:.2f} | {s['p95_latency_s']:.2f} | {s['agents']:.0f} | {fails} |"
        )
    md += [
        "",
        "| param | value | family | single | planner | handoff |",
        "|---|---|---|---|---|---|",
    ]
    for s in sweeps:
        md.append(
            f"| {s['param']} | {s['value']} | {s['family']} | {s['single']:.3f} | {s['planner']:.3f} | {s['handoff']:.3f} |"
        )
    p = Path(a.out)
    p.mkdir(exist_ok=True)
    (p / "bench.json").write_text(json.dumps(res, indent=2))
    (p / "bench.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    for arch, s in overall.items():
        print(arch, s)


if __name__ == "__main__":
    main()
