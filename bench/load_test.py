import asyncio
import math
import os
import sys
import time
from collections import Counter

import httpx


async def send_request(client: httpx.AsyncClient, api_key: str) -> httpx.Response | str:
    try:
        return await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
    except httpx.HTTPError as exc:
        return f"transport error: {exc!r}"


async def main(base_url: str, api_key: str, rpm_limit: int) -> None:
    n = rpm_limit * 3

    start = time.monotonic()
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        results = await asyncio.gather(
            *[send_request(client, api_key) for _ in range(n)]
        )
    elapsed = time.monotonic() - start

    responses = [r for r in results if isinstance(r, httpx.Response)]
    transport_errors = [r for r in results if isinstance(r, str)]

    # NEW: show exactly which status codes were returned
    status_counts = Counter(r.status_code for r in responses)
    print(f"status counts: {dict(status_counts)}")

    rejected = [r for r in responses if r.status_code == 429]
    admitted = [r for r in responses if r.status_code != 429]
    missing_retry_after = [
        r for r in rejected if "Retry-After" not in r.headers
    ]

    refill_per_second = rpm_limit / 60
    max_expected_admitted = rpm_limit + math.ceil(elapsed * refill_per_second)

    print(f"sent {n} requests at 3x rpm_limit ({rpm_limit}) in {elapsed:.2f}s")
    print(
        f"admitted (non-429): {len(admitted)} "
        f"(theoretical ceiling given elapsed time: {max_expected_admitted})"
    )
    print(f"rejected (429):     {len(rejected)}")
    print(f"transport errors:   {len(transport_errors)}")
    print(f"429s missing Retry-After: {len(missing_retry_after)}")

    failed = False

    if transport_errors:
        print(
            "FAIL: gateway dropped or errored on requests under load, "
            "should degrade with 429 instead"
        )
        failed = True

    if len(admitted) > max_expected_admitted:
        print(
            f"FAIL: {len(admitted)} admitted exceeds what capacity plus "
            f"real refill over {elapsed:.2f}s could allow "
            f"({max_expected_admitted})"
        )
        failed = True

    if missing_retry_after:
        print("FAIL: some 429 responses were missing Retry-After")
        failed = True

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(
        main(
            base_url=os.environ.get(
                "SB_LOAD_TEST_BASE_URL", "http://127.0.0.1:8000"
            ),
            api_key=os.environ["SB_LOAD_TEST_API_KEY"],
            rpm_limit=int(os.environ.get("SB_LOAD_TEST_RPM_LIMIT", "60")),
        )
    )