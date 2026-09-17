from switchboard.evals.pareto import build_pareto_report


def test_returns_one_point_per_min_length_with_matching_quality_data() -> None:
    points = build_pareto_report([5, 20], n_simulated=200)

    assert [p.min_length for p in points] == [5, 20]
    assert points[0].accuracy != points[1].accuracy


def test_cost_and_escalation_rate_move_together_across_thresholds() -> None:
    points = build_pareto_report([3, 20], n_simulated=2000)
    low, default = points

    assert low.escalation_rate < default.escalation_rate
    assert low.total_cost_micros < default.total_cost_micros


def test_deterministic_given_the_same_inputs() -> None:
    first = build_pareto_report([20], n_simulated=500)
    second = build_pareto_report([20], n_simulated=500)

    assert first == second