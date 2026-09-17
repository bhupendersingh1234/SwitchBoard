"""Replay recorded cascade legs against a different min_length threshold for
is_low_quality, using only what was actually recorded - no fresh model
calls, no re-running the request. Answers "what if min_length had been X"
against real outcomes rather than a fresh simulation.
"""

from dataclasses import dataclass

from switchboard.routing.cascade import CascadeLeg
from switchboard.routing.quality import is_low_quality


@dataclass
class ReplayComparison:
    total_legs: int
    original_low_quality_count: int
    replayed_low_quality_count: int
    flipped_to_good: list[str]  # was flagged low quality, wouldn't be under the new threshold
    flipped_to_bad: list[str]  # was fine, would now be flagged under the new threshold


def replay_at_min_length(legs: list[CascadeLeg], min_length: int) -> ReplayComparison:
    original_count = 0
    replayed_count = 0
    flipped_to_good: list[str] = []
    flipped_to_bad: list[str] = []

    for leg in legs:
        reconstructed = {
            "choices": [
                {
                    "message": {"content": leg.response_content},
                    "finish_reason": leg.finish_reason,
                }
            ]
        }
        replayed = is_low_quality(reconstructed, min_length=min_length)

        if leg.was_low_quality:
            original_count += 1
        if replayed:
            replayed_count += 1

        if leg.was_low_quality and not replayed:
            flipped_to_good.append(leg.response_content)
        elif not leg.was_low_quality and replayed:
            flipped_to_bad.append(leg.response_content)

    return ReplayComparison(
        total_legs=len(legs),
        original_low_quality_count=original_count,
        replayed_low_quality_count=replayed_count,
        flipped_to_good=flipped_to_good,
        flipped_to_bad=flipped_to_bad,
    )