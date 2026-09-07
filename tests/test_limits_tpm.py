import uuid

import pytest

from switchboard.limits.bucket import TokenBucket
from switchboard.limits.rate_limit import (
    RateLimitExceeded,
    estimate_request_tokens,
    refund_tpm_budget,
    reserve_tpm_budget,
)


def test_estimate_request_tokens_uses_max_tokens_when_provided() -> None:
    payload = {"messages": [{"role": "user", "content": "a" * 40}], "max_tokens": 300}
    assert estimate_request_tokens(payload, default_completion_estimate=512) == 10 + 300


def test_estimate_request_tokens_falls_back_to_default_completion_estimate() -> None:
    payload = {"messages": [{"role": "user", "content": "a" * 40}]}
    assert estimate_request_tokens(payload, default_completion_estimate=512) == 10 + 512


async def test_reserve_tpm_budget_allows_under_limit(redis) -> None:
    bucket = TokenBucket(redis)
    tenant_id = uuid.uuid4()
    await reserve_tpm_budget(bucket, tenant_id, tpm_limit=1000, estimated_tokens=600, now=1000.0)


async def test_reserve_tpm_budget_rejects_when_estimate_exceeds_remaining(redis) -> None:
    bucket = TokenBucket(redis)
    tenant_id = uuid.uuid4()
    await reserve_tpm_budget(bucket, tenant_id, tpm_limit=1000, estimated_tokens=600, now=1000.0)

    with pytest.raises(RateLimitExceeded):
        await reserve_tpm_budget(
            bucket, tenant_id, tpm_limit=1000, estimated_tokens=600, now=1000.0
        )


async def test_refund_tpm_budget_true_up_returns_unused_reservation(redis) -> None:
    bucket = TokenBucket(redis)
    tenant_id = uuid.uuid4()

    await reserve_tpm_budget(bucket, tenant_id, tpm_limit=1000, estimated_tokens=800, now=1000.0)
    await refund_tpm_budget(bucket, tenant_id, tpm_limit=1000, amount=800 - 150, now=1000.0)

    await reserve_tpm_budget(bucket, tenant_id, tpm_limit=1000, estimated_tokens=850, now=1000.0)