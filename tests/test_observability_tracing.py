import asyncio

from switchboard.observability.tracing import (
    generate_trace_id,
    get_trace_id,
    reset_trace_id,
    set_trace_id,
)


async def test_trace_id_is_isolated_between_concurrent_requests() -> None:
    seen: dict[str, str | None] = {}

    async def simulate_request(name: str, delay: float) -> None:
        token = set_trace_id(f"trace-{name}")
        try:
            await asyncio.sleep(delay)
            seen[name] = get_trace_id()
        finally:
            reset_trace_id(token)

    await asyncio.gather(
        simulate_request("a", 0.02),
        simulate_request("b", 0.01),
        simulate_request("c", 0.03),
    )

    assert seen == {"a": "trace-a", "b": "trace-b", "c": "trace-c"}


async def test_trace_id_is_unset_outside_any_request_context() -> None:
    assert get_trace_id() is None


def test_generate_trace_id_produces_unique_values() -> None:
    assert generate_trace_id() != generate_trace_id()