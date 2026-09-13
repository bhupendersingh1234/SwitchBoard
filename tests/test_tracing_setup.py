from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_request_produces_a_span_with_the_route_template_not_literal_path() -> None:
    exporter = InMemorySpanExporter()
    # Don't try to SET a new provider - conftest.py already imported switchboard.main,
    # which already configured one, and OpenTelemetry silently rejects a second
    # set_tracer_provider() call. Attach to whatever's already active instead.
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))

    app = FastAPI()

    @app.get("/items/{item_id}")
    async def get_item(item_id: str) -> dict:
        return {"item_id": item_id}

    FastAPIInstrumentor.instrument_app(app)
    client = TestClient(app)

    client.get("/items/abc")
    client.get("/items/xyz")

    spans = exporter.get_finished_spans()
    root_spans = [s for s in spans if s.parent is None]

    assert len(root_spans) == 2
    assert all(s.attributes["http.route"] == "/items/{item_id}" for s in root_spans)
    assert all(s.attributes["http.status_code"] == 200 for s in root_spans)

    FastAPIInstrumentor.uninstrument_app(app)