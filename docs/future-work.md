# Known gaps and future work

Every honest limitation named across this project's docs, in one place,
rather than scattered across eight files someone would otherwise have to
hunt through to piece together. Each one links back to where it was
originally named and why.

## No real fine-tuned model

`cascade_finetuned_model` defaults to `None` and stays unset. The full
pipeline to get from a cascade decision to a usable model is built and
verified (`docs/finetuning.md`) - collection, export, and the exact slot a
real model ID drops into - but step 3, actually submitting to OpenAI and
running the job, has never executed. Not because it needs resources
unavailable to the project, but because there's no real production traffic
yet to collect real `cascade_decisions` rows from. This resolves the moment
the gateway is actually serving requests with `collect_finetuning_data`
enabled for long enough to accumulate real data.

## The Pareto report's cost axis is still simulated

`evals/pareto.py` combines real eval data (quality axis) with simulated
traffic (cost axis) because `cascade_decisions` has no real rows - only two
inserted directly for M11's own verification. `routing/replay.py` exists
specifically so this can be rebuilt from real recorded legs instead of
simulation once real data exists (`docs/pareto-report.md`) - the mechanism
is there, the data isn't yet.

## The cascade-vs-classifier tradeoff is only measured on one axis

`docs/adr/0003` names the real cost of choosing a cascade over a
classifier: an escalated request pays for two sequential calls instead of
one. `bench/cascade_cost_demo.py` quantifies the *cost* side of that
tradeoff in dollars. Nothing in this project measures the *latency* side -
how much slower an escalated request actually is, end to end. That would
need either real traffic or a more deliberate latency simulation than
`routing/simulate.py` currently does (it models token counts and content,
not timing).

## `load_test.py` isn't part of the automated smoke coverage

`bench/cascade_cost_demo.py` got a smoke test because it's pure Python -
no server, no Redis, nothing external. `load_test.py` genuinely needs a
running server with Redis behind it to exercise the rate limiter for real,
which is a heavier setup than a unit test reasonably takes on. It remains
a manual-verification script, same as it's been since M4.

## The eval dataset is small, and that's a real limit, not just a caveat

14 hand-labeled cases (`evals/dataset.py`) is enough to catch a
catastrophic regression in `is_low_quality` and enough to have already
reversed one real conclusion about `min_length` (`docs/pareto-report.md`).
It is not enough to say the measured 50% accuracy generalizes to real
traffic with any confidence - `docs/evals.md` names this directly: the
dataset is deliberately adversarial, not representative, and growing it
from real observed failures (not more invented edge cases) is the stated
path forward once real traffic exists to observe failures from.

## No queue, so no live context-propagation problem yet

`docs/slo.md` walks through why a message queue would break the
`contextvars`-based trace ID this project uses, and what fixing it would
require - but there's no queue anywhere in this system today, so it's a
design constraint written down for whenever one gets added (a batch
endpoint, an async fine-tuning trigger), not a bug sitting in production
right now.

## Why this list exists at all

Every item here was named honestly at the point it came up, in the doc
where it was most relevant. This file doesn't add new information - it
just makes the shape of "what's real versus what's aspirational" visible
in one place, which is the thing a first-time reader (or an interviewer
skimming quickly) is least likely to reconstruct by reading eight separate
files in sequence.