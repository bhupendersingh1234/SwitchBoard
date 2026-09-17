from switchboard.evals.threshold_sweep import sweep_min_length


def test_sweep_returns_one_point_per_requested_min_length() -> None:
    points = sweep_min_length([5, 20, 100])

    assert [p.min_length for p in points] == [5, 20, 100]


def test_lower_threshold_reduces_false_positives_on_short_correct_answers() -> None:
    points = sweep_min_length([5, 20])
    low, default = points

    # The eval dataset's known false positives (M10) are short-but-correct
    # answers under the default min_length=20. A much lower threshold should
    # let at least some of them pass.
    assert low.false_positive_rate < default.false_positive_rate


def test_very_high_threshold_flags_almost_everything_as_low_quality() -> None:
    points = sweep_min_length([1000])
    point = points[0]

    # Nothing in the eval dataset is 1000 characters long, so every
    # actually-good case should now be a false positive.
    assert point.false_positive_rate == 1.0


def test_default_min_length_matches_the_measured_m10_baseline() -> None:
    points = sweep_min_length([20])
    point = points[0]

    assert round(point.accuracy, 3) == round(6 / 13, 3)