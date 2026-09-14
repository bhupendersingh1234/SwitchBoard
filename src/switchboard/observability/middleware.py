import time
from collections.abc import Awaitable, Callable

from opentelemetry import trace

from switchboard.observability.metrics import REQUEST_DURATION_SECONDS, REQUESTS_TOTAL
from switchboard.observability.tracing import generate_trace_id, reset_trace_id, set_trace_id

Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


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
        trace.get_current_span().set_attribute("sb.trace_id", trace_id)

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

        start = time.monotonic()
        status_holder = {"code": 500}

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - start
            route_obj = scope.get("route")
            route = route_obj.path if route_obj is not None else "unmatched"
            status_class = f"{status_holder['code'] // 100}xx"
            REQUESTS_TOTAL.labels(route=route, status_class=status_class).inc()
            REQUEST_DURATION_SECONDS.labels(route=route).observe(duration)