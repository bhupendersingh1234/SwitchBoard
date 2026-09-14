"""Demonstrates the actual cost tradeoff of cascade routing against the two
naive alternatives, using real pricing from the seeded models (M3) and the
real is_low_quality heuristic (M9) - not made-up numbers.

Run: python bench/cascade_cost_demo.py
"""

import random

from switchboard.accounting.pricing import compute_cost_micros
from switchboard.routing.quality import is_low_quality

CHEAP_INPUT, CHEAP_OUTPUT = 150_000, 600_000  # gpt-4o-mini, micros per mtok
EXPENSIVE_INPUT, EXPENSIVE_OUTPUT = 2_500_000, 10_000_000  # gpt-4o, micros per mtok

N_REQUESTS = 10_000
# Escalation rate is an assumption, not measured data - there's no eval harness
# yet (M10). 20% is a deliberately explicit, named guess: a minority of
# real-world requests are hard enough that a cheap model gives an incomplete
# or too-short answer, most aren't. This number is exactly what M10 exists to
# replace with something measured.
ASSUMED_HARD_REQUEST_RATE = 0.20


def _simulate_request(rng: random.Random) -> tuple[int, int, bool]:
    prompt_tokens = rng.randint(50, 500)
    is_hard = rng.random() < ASSUMED_HARD_REQUEST_RATE
    completion_tokens = rng.randint(20, 80) if is_hard else rng.randint(80, 300)
    return prompt_tokens, completion_tokens, is_hard


def _cheap_response_for(is_hard: bool, completion_tokens: int) -> dict:
    # A "hard" request gets a short, unfinished-looking answer from the cheap
    # model - which is exactly the signal is_low_quality is designed to catch.
    content = (
        ("short answer " * max(1, completion_tokens // 20))
        if is_hard
        else ("a complete and sufficiently detailed answer " * max(1, completion_tokens // 20))
    )
    finish_reason = "length" if is_hard else "stop"
    return {"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]}


def main() -> None:
    rng = random.Random(42)

    always_expensive_micros = 0
    always_cheap_micros = 0
    cascade_micros = 0
    escalations = 0

    for _ in range(N_REQUESTS):
        prompt_tokens, completion_tokens, is_hard = _simulate_request(rng)

        always_expensive_micros += compute_cost_micros(
            prompt_tokens, completion_tokens, EXPENSIVE_INPUT, EXPENSIVE_OUTPUT
        )
        always_cheap_micros += compute_cost_micros(
            prompt_tokens, completion_tokens, CHEAP_INPUT, CHEAP_OUTPUT
        )

        cheap_cost = compute_cost_micros(
            prompt_tokens, completion_tokens, CHEAP_INPUT, CHEAP_OUTPUT
        )
        cascade_micros += cheap_cost

        cheap_response = _cheap_response_for(is_hard, completion_tokens)
        if is_low_quality(cheap_response):
            escalations += 1
            cascade_micros += compute_cost_micros(
                prompt_tokens, completion_tokens, EXPENSIVE_INPUT, EXPENSIVE_OUTPUT
            )

    def usd(micros: int) -> str:
        return f"${micros / 1_000_000:,.2f}"

    print(f"Simulated {N_REQUESTS:,} requests (seed=42)")
    print(f"Assumed hard-request rate: {ASSUMED_HARD_REQUEST_RATE:.0%}")
    print()
    print(f"Always expensive (gpt-4o):        {usd(always_expensive_micros)}")
    print(f"Always cheap (gpt-4o-mini):        {usd(always_cheap_micros)}  (no quality guarantee)")
    print(f"Cascade:                           {usd(cascade_micros)}")
    print()
    print(f"Actual escalation rate observed:   {escalations / N_REQUESTS:.1%}")
    print(f"  ({escalations:,} of {N_REQUESTS:,} requests)")
    savings_vs_expensive = 1 - (cascade_micros / always_expensive_micros)
    premium_vs_cheap = (cascade_micros / always_cheap_micros) - 1
    print(f"Cascade saves vs always-expensive: {savings_vs_expensive:.1%}")
    print(f"Cascade costs more than always-cheap: {premium_vs_cheap:.1%}")
    print("  (the price of the quality guarantee)")


if __name__ == "__main__":
    main()