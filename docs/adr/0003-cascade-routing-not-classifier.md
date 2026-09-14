# 0003: Cascade routing instead of a classifier

## Status

Accepted

## Context

Switchboard's core value proposition is routing each request to the cheapest
model that meets a quality bar. The naturally "sophisticated" way to do this
is a classifier: given a prompt, predict up front whether the cheap model
would produce a good-enough answer, and route directly to the expensive one
when it wouldn't - skipping the cheap call entirely for requests predicted to
need it.

That requires labeled training data: pairs of (prompt, would-the-cheap-model-
have-succeeded). Switchboard has none at launch, and no eval harness yet
(M10) to generate it in bulk. A classifier trained on guesses or a handful of
hand-labeled examples would be making confident-looking routing decisions on
a foundation nobody has actually checked.

## Decision

Route with a cascade instead: call the cheap model first, run its response
through a quality check (`routing/quality.py`), and only call the expensive
model when that check fails (`routing/cascade.py`).

This has a bootstrapping property a classifier-first approach doesn't: every
cascade decision - the prompt, the cheap model's response, and whether it got
escalated - is itself a labeled example. The cascade doesn't just avoid
needing training data, it produces exactly the training data a future
classifier would need, as an ordinary byproduct of serving real traffic.

## Consequences

**Gains:**
- No cold start. The cascade works correctly from the first request, with no
  data collection phase before it can be trusted.
- Every request run through it generates real, labeled routing data for free.
- The routing decision is a simple, inspectable rule (`finish_reason` and
  response length - see `routing/quality.py`), not a black box. Anyone can
  read why a specific request escalated.

**Costs:**
- Latency: an escalated request pays for both calls, sequentially - the
  cheap model's full round trip, then the expensive model's. A trained
  classifier, once one exists, could route hard requests straight to the
  expensive model and pay that latency once instead of twice. The cascade
  demo (`bench/cascade_cost_demo.py`) quantifies the cost side of this
  tradeoff; it does not measure the latency side, which is a real gap this
  ADR is not claiming to close.
- The quality check itself is an unvalidated heuristic, not a measured one.
  `is_low_quality`'s signals (truncation, length) are defensible guesses
  about what correlates with a bad answer, not numbers checked against
  ground truth - because there is no ground truth yet. M10's eval harness is
  what turns this from "a reasonable guess" into "a measured threshold."

**Revisit when:** M10 exists and enough cascade decisions have accumulated to
train a classifier on. At that point the cascade's own output data becomes
the argument for building the thing it was chosen instead of - which is the
plan, not a contradiction.