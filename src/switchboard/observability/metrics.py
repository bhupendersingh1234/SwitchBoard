from prometheus_client import Counter, Histogram

REQUESTS_TOTAL = Counter("sb_requests_total", "Total requests handled", ["route", "status_class"])
REQUEST_DURATION_SECONDS = Histogram(
    "sb_request_duration_seconds", "Request duration in seconds", ["route"]
)
CACHE_HITS_TOTAL = Counter("sb_cache_hits_total", "Total cache hits")
CACHE_MISSES_TOTAL = Counter("sb_cache_misses_total", "Total cache misses")
TTFT_SECONDS = Histogram("sb_ttft_seconds", "Time to first streamed token, in seconds")
CASCADE_ESCALATIONS_TOTAL = Counter(
    "sb_cascade_escalations_total", "Total requests escalated from the cheap to the expensive model"
)
CASCADE_REQUESTS_TOTAL = Counter(
    "sb_cascade_requests_total", "Total requests routed through the cascade"
)