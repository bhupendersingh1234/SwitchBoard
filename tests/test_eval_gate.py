from switchboard.evals.dataset import CASES
from switchboard.evals.runner import run_eval
from switchboard.routing.quality import is_low_quality

# High-confidence bad cases: a truncated or filtered response reaching the
# user un-escalated is an unambiguous bug, not a known heuristic limitation.
# These must never appear in false_negatives, regardless of what else changes.
UNAMBIGUOUS_BAD_CASES = {
    "truncated_by_max_tokens",
    "truncated_mid_sentence",
    "content_filtered",
}

# Measured on the current heuristic (M10). This is a floor, not a target -
# if a change legitimately improves is_low_quality, raise this number to
# match the new measured score. If a change lowers it, that's the regression
# this gate exists to catch.
MINIMUM_ACCURACY = 0.50


def test_unambiguous_bad_cases_are_never_missed() -> None:
    result = run_eval(CASES, is_low_quality)

    missed = set(result.false_negatives) & UNAMBIGUOUS_BAD_CASES
    assert not missed, f"Unambiguous bad cases incorrectly passed as fine: {missed}"


def test_overall_accuracy_does_not_regress_below_measured_floor() -> None:
    result = run_eval(CASES, is_low_quality)

    assert result.accuracy >= MINIMUM_ACCURACY, (
        f"Accuracy {result.accuracy:.1%} dropped below the {MINIMUM_ACCURACY:.0%} floor "
        f"measured in M10. False positives: {result.false_positives}. "
        f"False negatives: {result.false_negatives}."
    )