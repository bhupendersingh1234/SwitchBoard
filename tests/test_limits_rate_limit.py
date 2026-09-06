import uuid

import pytest

from switchboard.limits.bucket import TokenBucket
from switchboard.limits.rate_limit import RateLimitExceeded, enforce_rpm_limit


async def test_enforce_rpm_limit_allows_under_limit(redis) -> None:
    bucket = TokenBucket(redis)
    tenant_id = uuid.uuid4()
    await enforce_rpm_limit(bucket, tenant_id, rpm_limit=5, now=1000.0)


async def test_enforce_rpm_limit_raises_with_retry_after_once_exhausted(redis) -> None:
    bucket = TokenBucket(redis)
    tenant_id = uuid.uuid4()
    for _ in range(5):
        await enforce_rpm_limit(bucket, tenant_id, rpm_limit=5, now=1000.0)

    with pytest.raises(RateLimitExceeded) as exc_info:
        await enforce_rpm_limit(bucket, tenant_id, rpm_limit=5, now=1000.0)
    assert exc_info.value.retry_after_seconds == 12