"""Demonstrates the actual cost tradeoff of cascade routing against the two
naive alternatives, using real pricing from the seeded models (M3) and the
real is_low_quality heuristic (M9) - not made-up numbers.

Run: python bench/cascade_cost_demo.py
"""

from switchboard.accounting.pricing import compute_cost_micros
from switchboard.routing.quality import is_low_quality
from switchboard.routing.simulate import (
    CHEAP_INPUT,
    CHEAP_OUTPUT,
    EXPENSIVE_INPUT,
    EXPENSIVE_OUTPUT,
    simulate_requests,
)

N_REQUESTS = 10_000
ASSUMED_HARD_REQUEST_RATE = 0.20


def main() -> None:
    requests = simulate_requests(N_REQUESTS, hard_request_rate=ASSUMED_HARD_REQUEST_RATE)

    always_expensive_micros = 0
    always_cheap_micros = 0
    cascade_micros = 0
    escalations = 0

    for req in requests:
        always_expensive_micros += compute_cost_micros(
            req.prompt_tokens, req.completion_tokens, EXPENSIVE_INPUT, EXPENSIVE_OUTPUT
        )
        cheap_cost = compute_cost_micros(
            req.prompt_tokens, req.completion_tokens, CHEAP_INPUT, CHEAP_OUTPUT
        )
        always_cheap_micros += cheap_cost
        cascade_micros += cheap_cost

        response = {
            "choices": [{"message": {"content": req.content}, "finish_reason": req.finish_reason}]
        }
        if is_low_quality(response):
            escalations += 1
            cascade_micros += compute_cost_micros(
                req.prompt_tokens, req.completion_tokens, EXPENSIVE_INPUT, EXPENSIVE_OUTPUT
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