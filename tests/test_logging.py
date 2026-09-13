import json
import logging

from switchboard.core.logging import JsonFormatter
from switchboard.observability.tracing import reset_trace_id, set_trace_id


def test_json_formatter_includes_trace_id_when_set() -> None:
    token = set_trace_id("trace-xyz")
    try:
        record = logging.LogRecord("t", logging.INFO, "f.py", 1, "hello", (), None)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_trace_id(token)

    assert payload["trace_id"] == "trace-xyz"


def test_json_formatter_omits_trace_id_when_not_set() -> None:
    record = logging.LogRecord("t", logging.INFO, "f.py", 1, "hello", (), None)
    payload = json.loads(JsonFormatter().format(record))

    assert "trace_id" not in payload


def test_json_formatter_still_includes_extras() -> None:
    record = logging.LogRecord("t", logging.INFO, "f.py", 1, "hello", (), None)
    record.dependency = "postgres"
    payload = json.loads(JsonFormatter().format(record))

    assert payload["msg"] == "hello"
    assert payload["dependency"] == "postgres"