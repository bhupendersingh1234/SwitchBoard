import asyncio
import uuid

from redis.asyncio import Redis

from switchboard.limits.bucket import TokenBucket


async def test_consume_allows_up_to_capacity_then_rejects(redis: Redis) -> None:
    bucket = TokenBucket(redis)
    key = f"bucket:{uuid.uuid4()}"

    for _ in range(5):
        allowed, _ = await bucket.consume(key, capacity=5, refill_per_second=0, now=1000.0)
        assert allowed is True

    allowed, remaining = await bucket.consume(key, capacity=5, refill_per_second=0, now=1000.0)
    assert allowed is False
    assert remaining == 0.0


async def test_consume_refills_over_simulated_time(redis: Redis) -> None:
    bucket = TokenBucket(redis)
    key = f"bucket:{uuid.uuid4()}"

    for _ in range(3):
        await bucket.consume(key, capacity=3, refill_per_second=1, now=1000.0)

    denied, _ = await bucket.consume(key, capacity=3, refill_per_second=1, now=1000.0)
    assert denied is False

    allowed, remaining = await bucket.consume(key, capacity=3, refill_per_second=1, now=1002.0)
    assert allowed is True
    assert remaining == 1.0


async def test_atomic_bucket_never_overadmits_under_concurrency(redis: Redis) -> None:
    bucket = TokenBucket(redis)
    key = f"bucket:{uuid.uuid4()}"
    capacity = 10

    results = await asyncio.gather(
        *[
            bucket.consume(key, capacity=capacity, refill_per_second=0, now=1000.0)
            for _ in range(50)
        ]
    )
    admitted = sum(1 for allowed, _ in results if allowed)
    assert admitted == capacity


async def _naive_consume(redis: Redis, key: str, capacity: int) -> bool:
    current = await redis.get(key)
    tokens = int(current) if current is not None else capacity
    await asyncio.sleep(0)
    if tokens <= 0:
        return False
    await redis.set(key, tokens - 1)
    return True


async def test_naive_get_then_set_overadmits_under_concurrency(redis: Redis) -> None:
    key = f"naive:{uuid.uuid4()}"
    capacity = 10

    results = await asyncio.gather(*[_naive_consume(redis, key, capacity) for _ in range(50)])
    admitted = sum(1 for allowed in results if allowed)
    assert admitted > capacity


async def test_refund_returns_tokens_to_the_bucket(redis: Redis) -> None:
    bucket = TokenBucket(redis)
    key = f"bucket:{uuid.uuid4()}"

    await bucket.consume(key, capacity=100, refill_per_second=0, now=1000.0, cost=60)
    await bucket.refund(key, capacity=100, refill_per_second=0, now=1000.0, amount=25)

    allowed, remaining = await bucket.consume(
        key, capacity=100, refill_per_second=0, now=1000.0, cost=65
    )
    assert allowed is True
    assert remaining == 0.0


async def test_refund_cannot_push_above_capacity(redis: Redis) -> None:
    bucket = TokenBucket(redis)
    key = f"bucket:{uuid.uuid4()}"

    await bucket.consume(key, capacity=100, refill_per_second=0, now=1000.0, cost=10)
    await bucket.refund(key, capacity=100, refill_per_second=0, now=1000.0, amount=50)

    _, remaining = await bucket.consume(key, capacity=100, refill_per_second=0, now=1000.0, cost=0)
    assert remaining == 100.0