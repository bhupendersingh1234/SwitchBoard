"""Shared simulated-traffic generator for cost/quality analysis (M9, M12).
Not real production data - there is none yet (see docs/finetuning.md,
docs/evals.md). Kept in one place so every script that needs simulated
requests uses the exact same generation logic, rather than each one
drifting slightly from the others over time.
"""

import random
from dataclasses import dataclass

CHEAP_INPUT, CHEAP_OUTPUT = 150_000, 600_000  # gpt-4o-mini, micros per mtok
EXPENSIVE_INPUT, EXPENSIVE_OUTPUT = 2_500_000, 10_000_000  # gpt-4o, micros per mtok

# Of the requests that are NOT hard (would complete normally either way),
# some fraction are genuinely short-form questions - yes/no, a single fact,
# a short code answer - the exact case the M10/M12 eval dataset found
# is_low_quality's length check gets wrong. Without modeling this, min_length
# has zero effect on any simulated outcome, since every simulated "good"
# response would always be long and every "bad" one always truncated - which
# would make a min_length sweep on this data meaningless, not just simple.
SHORT_FORM_RATE_AMONG_EASY_REQUESTS = 0.10


@dataclass
class SimulatedRequest:
    prompt_tokens: int
    completion_tokens: int
    is_hard: bool
    content: str
    finish_reason: str


def simulate_requests(
    n: int, hard_request_rate: float = 0.20, seed: int = 42
) -> list[SimulatedRequest]:
    rng = random.Random(seed)
    requests = []
    for _ in range(n):
        prompt_tokens = rng.randint(50, 500)
        is_hard = rng.random() < hard_request_rate

        if is_hard:
            completion_tokens = rng.randint(20, 80)
            content = "short answer " * max(1, completion_tokens // 20)
            finish_reason = "length"
        elif rng.random() < SHORT_FORM_RATE_AMONG_EASY_REQUESTS:
            completion_tokens = rng.randint(1, 5)
            content = "Yes."
            finish_reason = "stop"
        else:
            completion_tokens = rng.randint(80, 300)
            content = "a complete and sufficiently detailed answer " * max(
                1, completion_tokens // 20
            )
            finish_reason = "stop"

        requests.append(
            SimulatedRequest(prompt_tokens, completion_tokens, is_hard, content, finish_reason)
        )
    return requests