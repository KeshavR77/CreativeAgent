"""A/B divergence harness (Stage 10, §10 stretch).

Measures the product's core claim — that Conceptial ideation yields a MORE
divergent set of directions than the plain-Claude (``claude_high_temp``)
baseline — using the PRODUCTION divergence metric verbatim
(``app.services.divergence.divergence_report``), never a forked copy. This module
is pure aggregation + a graph-driving helper; the runnable CLI is
``scripts/ab_divergence.py``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.divergence import active_directions, divergence_report  # production metric — never reimplement

# Arm names == the ``brain`` each ideator stamps on its directions, so a run's
# recorded brains can be checked against the arm it was meant to exercise.
ARM_CONCEPTIAL = "conceptial"
ARM_CLAUDE = "claude_high_temp"
ARM_MOCK = "mock"


@dataclass
class RunRecord:
    """One run's divergence, from the production metric over its directions."""

    arm: str
    min: float
    mean: float
    warning: bool
    n_directions: int
    brains: list[str] = field(default_factory=list)


@dataclass
class ArmSummary:
    arm: str
    runs: int
    mean_min: float
    mean_mean: float
    worst_min: float
    warn_rate: float
    brain_counts: dict[str, int]


def divergence_record(arm: str, directions) -> RunRecord:
    """Build a RunRecord for one run using ``app.services.divergence`` verbatim."""
    directions = list(directions)
    report = divergence_report(directions)  # {min, mean, warning, scores}
    return RunRecord(
        arm=arm,
        min=report["min"],
        mean=report["mean"],
        warning=report["warning"],
        n_directions=len(directions),
        brains=[getattr(d, "brain", "?") for d in directions],
    )


def summarize_arm(arm: str, records) -> ArmSummary:
    """Aggregate every RunRecord for ``arm`` into an ArmSummary."""
    rs = [r for r in records if r.arm == arm]
    if not rs:
        raise ValueError(f"no runs recorded for arm {arm!r}")
    n = len(rs)
    brain_counts: dict[str, int] = {}
    for r in rs:
        for b in r.brains:
            brain_counts[b] = brain_counts.get(b, 0) + 1
    return ArmSummary(
        arm=arm,
        runs=n,
        mean_min=sum(r.min for r in rs) / n,
        mean_mean=sum(r.mean for r in rs) / n,
        worst_min=min(r.min for r in rs),
        warn_rate=sum(1 for r in rs if r.warning) / n,
        brain_counts=brain_counts,
    )


def compare(records) -> dict:
    """JSON-serializable comparison over every arm present, plus a treatment-vs-
    baseline verdict (Conceptial vs claude_high_temp) when both arms ran."""
    records = list(records)
    arms = sorted({r.arm for r in records})
    summaries = {a: summarize_arm(a, records) for a in arms}
    out: dict = {"arms": {a: asdict(s) for a, s in summaries.items()}}
    treatment, baseline = summaries.get(ARM_CONCEPTIAL), summaries.get(ARM_CLAUDE)
    if treatment and baseline:
        out["verdict"] = {
            "treatment": ARM_CONCEPTIAL,
            "baseline": ARM_CLAUDE,
            "mean_divergence_delta": treatment.mean_mean - baseline.mean_mean,
            "min_divergence_delta": treatment.mean_min - baseline.mean_min,
            "treatment_more_divergent": treatment.mean_mean > baseline.mean_mean,
        }
    return out


def human_summary(comparison: dict) -> str:
    """A terse human-readable rendering of a ``compare()`` result."""
    lines = ["A/B divergence report", "=" * 21]
    for arm, s in comparison["arms"].items():
        lines.append(
            f"  {arm:16s} runs={s['runs']:2d}  mean={s['mean_mean']:.3f}  "
            f"min={s['mean_min']:.3f}  worst_min={s['worst_min']:.3f}  "
            f"warn_rate={s['warn_rate']:.0%}  brains={s['brain_counts']}"
        )
    v = comparison.get("verdict")
    if v:
        verb = "MORE" if v["treatment_more_divergent"] else "NOT more"
        lines.append(
            f"\nVerdict: {v['treatment']} is {verb} divergent than {v['baseline']} "
            f"(Δmean={v['mean_divergence_delta']:+.3f}, Δmin={v['min_divergence_delta']:+.3f})."
        )
    return "\n".join(lines)


async def run_arm(run_manager, arm: str, brief, n: int, *, id_prefix: str = "ab") -> list[RunRecord]:
    """Drive ``n`` runs to Gate 2 and record each run's production divergence.

    The CALLER configures the environment (keys) so ``arm`` is the ideator in
    effect; this only labels + measures. Returns one RunRecord per run.
    """
    records: list[RunRecord] = []
    for i in range(n):
        pid = f"{id_prefix}-{arm}-{i}"
        await (await run_manager.start(pid, brief))
        await (await run_manager.resume(pid, {"action": "approve"}))
        view = await run_manager.get_view(pid)
        directions = view.directions if view else []
        # A run that lost territories can end with <2 active directions, for which
        # divergence is undefined (divergence_report raises). Skip it rather than
        # crash the whole measurement — the caller just gets one fewer record.
        if len(active_directions(directions)) < 2:
            continue
        records.append(divergence_record(arm, directions))
    return records
