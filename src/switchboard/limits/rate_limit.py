import math
import time
import uuid

from switchboard.limits.bucket import TokenBucket


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limit exceeded, retry after {retry_after_seconds}s")


async def enforce_rpm_limit(
    bucket: TokenBucket, tenant_id: uuid.UUID, rpm_limit: int, now: float | None = None
) -> None:
    if now is None:
        now = time.time()
    allowed, _ = await bucket.consume(
        key=f"ratelimit:rpm:{tenant_id}",
        capacity=rpm_limit,
        refill_per_second=rpm_limit / 60,
        now=now,
    )
    if not allowed:
        raise RateLimitExceeded(retry_after_seconds=math.ceil(60 / rpm_limit))