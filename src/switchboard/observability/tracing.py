import contextvars
import uuid

_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)


def get_trace_id() -> str | None:
    return _trace_id_var.get()


def generate_trace_id() -> str:
    return uuid.uuid4().hex


def set_trace_id(trace_id: str) -> contextvars.Token:
    return _trace_id_var.set(trace_id)


def reset_trace_id(token: contextvars.Token) -> None:
    _trace_id_var.reset(token)