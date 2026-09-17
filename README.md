# Switchboard

A self-hostable LLM gateway that routes each request to the cheapest model
meeting a quality bar, with the production infrastructure a real gateway
needs around it: per-tenant auth, rate limits, budgets, cost accounting,
resilience, streaming, caching, observability, and an eval-gated routing
policy - not a thin proxy with a demo bolted on.

## Why this exists

Calling an LLM API directly gets you a model. It doesn't get you
tenant isolation, a way to stop one caller from burning a shared rate
limit, a record of what anything actually cost, or a plan for what happens
when the provider is slow or down. Switchboard is the layer that sits
between an application and a model provider and answers those questions -
and specifically, it tries to answer the most expensive one honestly:
*which* model should handle this request, given that the cheap one is
usually fine and the expensive one is only sometimes worth it.

## Core mechanism: cascade routing, not a classifier

The obvious way to route by cost is a classifier that predicts up front
whether a cheap model would produce a good answer. That needs labeled
training data this project doesn't have. Instead, Switchboard cascades:
try the cheapest tier, run its response through a quality check, escalate
only if it fails. This has a bootstrapping property a classifier-first
design doesn't - every cascade decision is itself a labeled example,
so the mechanism chosen to avoid needing training data ends up producing
exactly the training data a future classifier would need
(`docs/adr/0003-cascade-routing-not-classifier.md`).

The quality check itself (`finish_reason` and response length) is an
explicit heuristic, not a trained model - and it's been measured, not just
assumed. An eval harness with a hand-labeled, deliberately adversarial
dataset gates CI on it (`docs/evals.md`), and a Pareto report combines that
eval data with simulated cost data to show what changing the threshold
actually trades off (`docs/pareto-report.md`). The honest number: the
current default is measurably not the cheapest option available, and it's
kept anyway, because the cheaper option trades away the system's actual
purpose (catching bad answers) for a metric that's easier to move (overall
accuracy).

## Architecture
Request
│
├─ auth (hashed, prefixed API keys, tenant isolation)
├─ budget check (monthly spend cap)
├─ rate limit (Redis Lua token bucket, atomic under concurrency)
├─ cache lookup (exact-match, tenant-scoped, temperature=0 only)
├─ cascade routing (cheap tier → quality check → escalate if needed)
│ └─ each tier wrapped in: retry w/ jitter → circuit breaker → failover/hedge
├─ streaming (SSE passthrough, cancellation-safe, TTFT tracked)
├─ accounting (per-tier cost, immutable historical pricing snapshots)
└─ observability (OTel traces, Prometheus metrics, structured logs -
all correlated by one trace ID, response header to log line to span)


Layered as a Python package under `src/switchboard/`:

| Package | Responsibility |
|---|---|
| `api/` | FastAPI routes and request-scoped dependencies |
| `auth/` | API key generation, hashing, tenant resolution |
| `accounting/` | Pricing math, usage ledger |
| `limits/` | Redis-backed rate limiting and budget enforcement |
| `cache/` | Exact-match response cache |
| `providers/` | OpenAI client plus resilience wrappers (retry, circuit breaker, failover, hedging) |
| `resilience/` | The primitives those wrappers are built from |
| `routing/` | Cascade logic, quality heuristic, fine-tuning export, threshold replay |
| `evals/` | Hand-labeled eval dataset, runner, threshold sweep, Pareto report |
| `observability/` | Trace ID propagation, OTel setup, Prometheus metrics, ASGI middleware |
| `db/` | SQLAlchemy models, Alembic migrations |

## Running it

```bash
docker compose up -d          # Postgres, Redis, the API, and a one-shot migration runner
pip install -e ".[dev]"
alembic upgrade head
pytest -q
```

Configuration is environment-variable driven with an `SB_` prefix
(`SB_DATABASE_URL`, `SB_REDIS_URL`, `SB_OPENAI_API_KEY`, and so on) via
`core/config.py`. See `docker-compose.yml` for the full set used in CI.

## Verifying it yourself

- `pytest -q` - the full test suite, including the CI eval gate
  (`tests/test_eval_gate.py`)
- `python -m switchboard.evals.run` - prints the current eval accuracy and
  which specific cases are failing, not just a pass/fail
- `python bench/load_test.py` - proves the rate limiter holds under
  concurrent load with an honest theoretical ceiling to check against
- `python bench/cascade_cost_demo.py` - the cascade's actual cost tradeoff
  against always-cheap and always-expensive, on simulated traffic
- `make dashboard` - regenerates the Grafana dashboard JSON from its Python
  source (`deploy/grafana/switchboard.dashboard.py`)

## Design decisions worth reading

Architecture Decision Records, in `docs/adr/`:

- **0001** - liveness vs. readiness probe separation
- **0002** - Alembic owns the schema; `create_all()` never runs
- **0003** - cascade routing instead of a classifier, and what that trade
  actually costs

Standalone docs, in `docs/`:

- **`slo.md`** - availability, latency, and TTFT targets, with the exact
  multi-instance-safe PromQL for each, and why naively averaging p99s
  across instances is wrong
- **`evals.md`** - why the eval harness is hand-labeled and rule-based
  rather than an LLM judge, and the Goodhart's-law risk of tuning against
  its own dataset
- **`finetuning.md`** - the real pipeline from a cascade decision to a
  usable fine-tuned model, and an honest line between what's built and
  verified versus what still needs real production traffic to complete
- **`pareto-report.md`** - the actual cost/quality tradeoff at different
  quality-check thresholds, and why the cheaper option was set aside
  rather than missed

## What's deliberately not here

No real fine-tuned model exists - there's no production traffic yet to
train one on (`docs/finetuning.md`). No LLM-as-judge evaluation - the eval
harness is rule-based on purpose, for a CI gate that needs to be fast, free,
and deterministic (`docs/evals.md`). No queue or async processing - and so
no queue-boundary context propagation problem to solve yet, though
`docs/slo.md` names the design constraint for when one gets added. Naming
these explicitly matters more here than it would elsewhere: this project's
own discipline throughout has been to state a limitation precisely rather
than let a demo imply more than what's actually been verified.