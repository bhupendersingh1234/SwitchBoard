"""Sweep is_low_quality's min_length across a range and measure eval
accuracy/FPR/FNR at each value, using the M10 eval dataset. This is the
"quality" axis of the Pareto tradeoff between threshold choice and
escalation behavior - reusing the same eval harness M10 already proved
correct, not a new measurement approach.
"""

from dataclasses import dataclass
from functools import partial

from switchboard.evals.dataset import CASES
from switchboard.evals.runner import run_eval
from switchboard.routing.quality import is_low_quality


@dataclass
class ThresholdPoint:
    min_length: int
    accuracy: float
    false_positive_rate: float
    false_negative_rate: float


def sweep_min_length(min_lengths: list[int]) -> list[ThresholdPoint]:
    points = []
    for min_length in min_lengths:
        quality_fn = partial(is_low_quality, min_length=min_length)
        result = run_eval(CASES, quality_fn)
        points.append(
            ThresholdPoint(
                min_length=min_length,
                accuracy=result.accuracy,
                false_positive_rate=result.false_positive_rate,
                false_negative_rate=result.false_negative_rate,
            )
        )
    return points