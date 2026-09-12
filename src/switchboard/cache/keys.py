import hashlib
import json
import uuid


def is_cacheable(payload: dict) -> bool:
    return payload.get("temperature") == 0 and not payload.get("stream")


def compute_cache_key(tenant_id: uuid.UUID, payload: dict) -> str:
    relevant = {
        "model": payload.get("model"),
        "messages": payload.get("messages"),
        "temperature": payload.get("temperature"),
        "max_tokens": payload.get("max_tokens"),
        "top_p": payload.get("top_p"),
    }
    canonical = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"cache:{tenant_id}:{digest}"