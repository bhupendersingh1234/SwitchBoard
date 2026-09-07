import math
import time
import uuid

from switchboard.limits.bucket import TokenBucket


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limit exceeded, retry after {retry_after_seconds}s")


def _retry_after_seconds(deficit: float, refill_per_second: float) -> int:
    return max(1, math.ceil(deficit / refill_per_second))


async def enforce_rpm_limit(
    bucket: TokenBucket, tenant_id: uuid.UUID, rpm_limit: int, now: float | None = None
) -> None:
    if now is None:
        now = time.time()
    refill_per_second = rpm_limit / 60
    allowed, remaining = await bucket.consume(
        key=f"ratelimit:rpm:{tenant_id}",
        capacity=rpm_limit,
        refill_per_second=refill_per_second,
        now=now,
    )
    if not allowed:
        raise RateLimitExceeded(_retry_after_seconds(1 - remaining, refill_per_second))


def estimate_request_tokens(payload: dict, default_completion_estimate: int) -> int:
    messages = payload.get("messages", [])
    prompt_chars = sum(
        len(m.get("content", "")) for m in messages if isinstance(m.get("content"), str)
    )
    estimated_prompt_tokens = max(1, prompt_chars // 4)
    estimated_completion_tokens = int(payload.get("max_tokens", default_completion_estimate))
    return estimated_prompt_tokens + estimated_completion_tokens


async def reserve_tpm_budget(
    bucket: TokenBucket,
    tenant_id: uuid.UUID,
    tpm_limit: int,
    estimated_tokens: int,
    now: float | None = None,
) -> None:
    if now is None:
        now = time.time()
    refill_per_second = tpm_limit / 60
    allowed, remaining = await bucket.consume(
        key=f"ratelimit:tpm:{tenant_id}",
        capacity=tpm_limit,
        refill_per_second=refill_per_second,
        now=now,
        cost=estimated_tokens,
    )
    if not allowed:
        deficit = estimated_tokens - remaining
        raise RateLimitExceeded(_retry_after_seconds(deficit, refill_per_second))


async def refund_tpm_budget(
    bucket: TokenBucket,
    tenant_id: uuid.UUID,
    tpm_limit: int,
    amount: int,
    now: float | None = None,
) -> None:
    if amount <= 0:
        return
    if now is None:
        now = time.time()
    await bucket.refund(
        key=f"ratelimit:tpm:{tenant_id}",
        capacity=tpm_limit,
        refill_per_second=tpm_limit / 60,
        now=now,
        amount=amount,
    )