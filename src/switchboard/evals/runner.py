from collections.abc import Callable
from dataclasses import dataclass

from switchboard.evals.dataset import EvalCase


@dataclass
class EvalResult:
    total: int
    correct: int
    actually_good_count: int
    actually_bad_count: int
    false_positives: list[str]  # heuristic said low quality, but it was actually good
    false_negatives: list[str]  # heuristic said fine, but it was actually bad

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def false_positive_rate(self) -> float:
        # Of the cases that were actually good, what fraction did we needlessly
        # escalate on? Costs money, not correctness.
        if not self.actually_good_count:
            return 0.0
        return len(self.false_positives) / self.actually_good_count

    @property
    def false_negative_rate(self) -> float:
        # Of the cases that were actually bad, what fraction did we fail to
        # catch? Costs a bad answer reaching the user.
        if not self.actually_bad_count:
            return 0.0
        return len(self.false_negatives) / self.actually_bad_count


def run_eval(cases: list[EvalCase], is_low_quality: Callable[[dict], bool]) -> EvalResult:
    correct = 0
    false_positives = []
    false_negatives = []
    actually_good_count = sum(1 for c in cases if c.actually_good)
    actually_bad_count = len(cases) - actually_good_count

    for case in cases:
        predicted_good = not is_low_quality(case.response)

        if predicted_good == case.actually_good:
            correct += 1
        elif case.actually_good and not predicted_good:
            false_positives.append(case.name)
        elif not case.actually_good and predicted_good:
            false_negatives.append(case.name)

    return EvalResult(
        total=len(cases),
        correct=correct,
        actually_good_count=actually_good_count,
        actually_bad_count=actually_bad_count,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )