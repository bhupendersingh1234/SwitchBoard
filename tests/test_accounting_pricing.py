from switchboard.accounting.pricing import compute_cost_micros

GPT_4O_INPUT = 2_500_000
GPT_4O_OUTPUT = 10_000_000
GPT_4O_MINI_INPUT = 150_000
GPT_4O_MINI_OUTPUT = 600_000


def test_compute_cost_micros_matches_expected_dollar_amount() -> None:
    cost = compute_cost_micros(1000, 500, GPT_4O_INPUT, GPT_4O_OUTPUT)
    assert cost == 7_500  # $0.0075


def test_compute_cost_micros_zero_tokens_is_zero_cost() -> None:
    assert compute_cost_micros(0, 0, GPT_4O_INPUT, GPT_4O_OUTPUT) == 0


def test_compute_cost_micros_scales_linearly_with_tokens() -> None:
    small = compute_cost_micros(100, 0, GPT_4O_MINI_INPUT, GPT_4O_MINI_OUTPUT)
    large = compute_cost_micros(1000, 0, GPT_4O_MINI_INPUT, GPT_4O_MINI_OUTPUT)
    assert large == small * 10


def test_compute_cost_micros_floors_fractional_micros() -> None:
    assert compute_cost_micros(1, 0, GPT_4O_MINI_INPUT, GPT_4O_MINI_OUTPUT) == 0