# Fine-tuning workflow (M11)

How a fine-tuned model actually becomes the cascade's cheapest tier, end to
end. This documents the real workflow; steps 1-2 are built and verified
against a real database in this repo's history. Step 3 (submitting to
OpenAI) has not actually been run - not because it requires a budget or key
neither this project nor its maintainer has access to, but because it
requires a real API key and a live network call, which the assistant
building this repo does not have access to in its own environment. That is
a constraint on this conversation, not a constraint on the project: running
step 3 for real is something the project's maintainer can do directly,
independent of anything here, whenever there is real cascade_decisions data
worth training on.

## The pipeline

1. **Collect** - with `collect_finetuning_data: true` set, every cascade
   request writes one row per tier tried to `cascade_decisions`
   (`routing/record.py`): the prompt, that tier's response, which model
   answered, and whether the quality check flagged it. Off by default -
   this is real conversation content, and storing it is an explicit choice,
   not a side effect.

2. **Export** - `python -m switchboard.routing.export_cli --output
   training_data.jsonl` queries every recorded decision and writes the ones
   that passed the quality check as OpenAI fine-tuning JSONL
   (`routing/finetune_export.py`). Verified against a real Postgres
   database in this repo's history: real rows in, a real valid JSONL file
   out, the low-quality row correctly excluded.

3. **Train** - upload `training_data.jsonl` and start a fine-tuning job
   through OpenAI's own API or dashboard. This is OpenAI's infrastructure
   doing the actual training - nothing in this gateway needs to know how
   fine-tuning works internally, only how to produce the input it expects
   and how to use the output.

4. **Deploy** - OpenAI returns a model ID like
   `ft:gpt-4o-mini-2024-07-18:org::abc123`. Set
   `cascade_finetuned_model` to that string. `main.py` puts it first in the
   cascade's tier list if set:

```python
   cascade_models = [settings.cascade_cheap_model, settings.cascade_expensive_model]
   if settings.cascade_finetuned_model:
       cascade_models = [settings.cascade_finetuned_model, *cascade_models]

   cascade_provider = CascadeProvider(provider, models=cascade_models)
```

   `CascadeProvider` (M11) doesn't need to know or care that this model
   name came from a fine-tuning job rather than being a stock OpenAI
   model - it's just one more string in an ordered list, tried first,
   escalated past exactly the same way any other tier would be.

## What this actually closes

The M9 ADR's own "revisit when" clause: "when M10 exists and enough
cascade decisions have accumulated to train a classifier on... the
cascade's own output data becomes the argument for building the thing it
was chosen instead of." Steps 1-2 are that argument made real - the
cascade now produces its own training data as an ordinary byproduct of
serving traffic, exactly as that ADR predicted it would.

## What isn't closed

There's no real fine-tuned model yet, for one genuine project-level reason
and one unrelated tooling reason - worth keeping separate rather than
blurring together:

- **Real limitation:** no production traffic exists to collect real
  decisions from. This project has never been deployed to real users, so
  `cascade_decisions` has no real rows - only the two inserted directly
  for verification during M11. This is true regardless of who holds an
  API key; it only resolves once the gateway is actually serving traffic.
- **Not a project limitation:** step 3 (submitting `training_data.jsonl`
  to OpenAI and running the fine-tuning job) has not been executed here
  because doing so needs a live network call this environment cannot make -
  not because it needs resources unavailable to the project or its
  maintainer. Once real `cascade_decisions` rows exist, running step 3 is
  a normal, unblocked action the maintainer can take directly.

`cascade_finetuned_model` defaults to `None` and stays unset until that
happens. What's real and verified here is everything up to that point: the
collection, the export, and the exact point where a real model ID slots in
the moment one exists.