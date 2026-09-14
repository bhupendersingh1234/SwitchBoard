# Switchboard SLOs

These are the service level objectives for Switchboard as a gateway, and the
exact PromQL each one is measured with. Every query here sums raw counters or
histogram buckets across all instances *before* deriving a rate or a
percentile - never after. See "Why not average p99s" below for why that
distinction is the difference between a correct number and a plausible-looking
wrong one.

## Availability

**SLO: 99.5% of requests return a non-5xx response, over a rolling 30-day window.**

```promql
sum(rate(sb_requests_total{status_class!="5xx"}[30d]))
/
sum(rate(sb_requests_total[30d]))
```

0.5% error budget over 30 days is about 3.6 hours of full-outage-equivalent
downtime, or a proportionally larger amount of partial degradation. A 4xx
(bad request, invalid key, budget exceeded) is a correct response to a bad
input, not a reliability failure - only 5xx counts against this budget,
which is exactly why `status_class` exists as a label rather than the exact
status code.

## Latency

**SLO: 95% of non-streaming requests complete within 5 seconds.**

```promql
histogram_quantile(0.95,
  sum(rate(sb_request_duration_seconds_bucket{route="/v1/chat/completions"}[5m]))
  by (le)
) < 5
```

5 seconds is deliberately well inside the 10-second hard request deadline
(`request_deadline_s`, M5) - the deadline is where we give up and return 504;
the SLO is where a request still succeeded but the experience was starting to
degrade. A system that only tracks the hard failure point can't tell "healthy"
from "barely surviving."

## Time to first token (streaming)

**SLO: 95% of streaming requests emit a first token within 1.5 seconds.**

```promql
histogram_quantile(0.95, sum(rate(sb_ttft_seconds_bucket[5m])) by (le)) < 1.5
```

TTFT is tracked separately from overall request duration because it answers a
different question. A streaming request that takes 8 seconds *total* but
showed the first word at 200ms reads as fast to the person watching it type;
a request that takes 2 seconds total but shows nothing until the last 100ms
reads as slow, even though it finished sooner. Total duration and perceived
responsiveness are genuinely different things once a response is allowed to
stream.

## Why not average p99s

Percentiles are not additive - `avg(p99_instance_a, p99_instance_b)` is not
the fleet's real p99, it's just an average of two numbers that happen to be
percentiles. An instance serving 10 requests with one slow outlier and an
instance serving 10,000 requests that are all fast would contribute *equally*
to that average, even though the second instance's traffic should dominate
the true answer. Every query above sums `rate(..._bucket[...])` across
instances first (via `by (le, ...)`, which keeps the histogram buckets but
drops the `instance` label), and calls `histogram_quantile` exactly once, on
the combined distribution. There is no intermediate per-instance percentile
anywhere to average by mistake - the query is structurally incapable of the
wrong answer, not just written carefully to avoid it.

## Context propagation and why it breaks across a queue

Context propagation is how a trace ID (and the rest of a trace's context)
survives crossing a boundary between processes. Across a synchronous HTTP
call, this is what `TraceIdMiddleware` does: read the ID from an incoming
header if present, generate one if not, and put it somewhere every log line
and span in this request can see (M8). It works because the header travels
with the request automatically - there's no separate step where anyone has
to remember to carry it along.

A queue breaks that automatic part. Publishing a message onto a queue and
having a worker pick it up later is not one continuous call - it's two
unrelated events in two unrelated processes, potentially seconds or hours
apart, possibly on a different machine entirely. The `contextvars`-based
trace ID this project uses (verified in M8 to correctly isolate concurrent
*in-process* requests from each other) does not and cannot survive that gap
on its own - a `ContextVar` is process-local memory, and a queue message is
just bytes. If a worker doesn't explicitly read a trace ID back out of the
message and call `set_trace_id` with it, the work that message triggers
becomes a new, disconnected trace with no link back to the request that
enqueued it - which directly breaks this milestone's own promise of
reconstructing every routing decision for a request from its trace ID.

Switchboard has no queue today, so this isn't a live bug - it's a design
constraint for whenever one gets added (a batch endpoint, an async
fine-tuning job for the cheap tier in a later milestone, anything that
enqueues work rather than handling it inline). The fix, if that day comes,
is the same shape as `TraceIdMiddleware` itself: serialize the trace ID into
the message when publishing, and call `set_trace_id` with it as the very
first thing the consumer does when picking the message back up - manually
re-creating the propagation an HTTP header gives for free.

## Cache hit ratio - a target, not an SLO

```promql
sum(rate(sb_cache_hits_total[5m]))
/
(sum(rate(sb_cache_hits_total[5m])) + sum(rate(sb_cache_misses_total[5m])))
```

Deliberately not framed as an SLO above. An SLO is a reliability promise to
whoever depends on this service; a low cache hit ratio doesn't break anyone's
request, it just makes it more expensive to serve - it's a cost-efficiency
target we watch, not a commitment we can be said to violate.