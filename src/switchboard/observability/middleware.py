import time
from collections.abc import Awaitable, Callable

from prometheus_client import Counter, Histogram

from switchboard.observability.tracing import (
    generate_trace_id,
    reset_trace_id,
    set_trace_id,
)

Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

REQUESTS_TOTAL = Counter(
    "switchboard_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"],
)

REQUEST_DURATION_SECONDS = Histogram(
    "switchboard_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
)


class TraceIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        incoming = headers.get(b"x-trace-id")
        trace_id = incoming.decode() if incoming else generate_trace_id()
        token = set_trace_id(trace_id)

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-trace-id", trace_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            reset_trace_id(token)


class MetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        method = scope["method"]
        route = scope.get("path", "unknown")
        status_code = 500

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            REQUESTS_TOTAL.labels(
                method=method,
                route=route,
                status=str(status_code),
            ).inc()

            REQUEST_DURATION_SECONDS.labels(
                method=method,
                route=route,
            ).observe(time.perf_counter() - start)