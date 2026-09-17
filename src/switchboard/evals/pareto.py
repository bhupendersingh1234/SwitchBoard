"""Pareto report: quality (evals/threshold_sweep.py, real hand-labeled data)
and cost (simulated traffic, routing/simulate.py) at the same min_length
values, in one place - so a threshold choice gets judged on both axes
together, not argued about with two separate numbers from two separate
scripts.
"""

from dataclasses import dataclass

from switchboard.accounting.pricing import compute_cost_micros
from switchboard.evals.threshold_sweep import sweep_min_length
from switchboard.routing.quality import is_low_quality
from switchboard.routing.simulate import (
    CHEAP_INPUT,
    CHEAP_OUTPUT,
    EXPENSIVE_INPUT,
    EXPENSIVE_OUTPUT,
    simulate_requests,
)


@dataclass
class ParetoPoint:
    min_length: int
    accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    escalation_rate: float
    total_cost_micros: int


def build_pareto_report(min_lengths: list[int], n_simulated: int = 10_000) -> list[ParetoPoint]:
    quality_by_threshold = {p.min_length: p for p in sweep_min_length(min_lengths)}
    requests = simulate_requests(n_simulated)

    points = []
    for min_length in min_lengths:
        total_cost = 0
        escalations = 0
        for req in requests:
            total_cost += compute_cost_micros(
                req.prompt_tokens, req.completion_tokens, CHEAP_INPUT, CHEAP_OUTPUT
            )
            response = {
                "choices": [
                    {"message": {"content": req.content}, "finish_reason": req.finish_reason}
                ]
            }
            if is_low_quality(response, min_length=min_length):
                escalations += 1
                total_cost += compute_cost_micros(
                    req.prompt_tokens, req.completion_tokens, EXPENSIVE_INPUT, EXPENSIVE_OUTPUT
                )

        quality = quality_by_threshold[min_length]
        points.append(
            ParetoPoint(
                min_length=min_length,
                accuracy=quality.accuracy,
                false_positive_rate=quality.false_positive_rate,
                false_negative_rate=quality.false_negative_rate,
                escalation_rate=escalations / n_simulated,
                total_cost_micros=total_cost,
            )
        )
    return points