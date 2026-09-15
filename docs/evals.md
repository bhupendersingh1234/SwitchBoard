# Eval methodology

This documents how `evals/` works, why it's built the way it is, and how to
extend it - written down once rather than re-derived every time it comes up.

## What's being evaluated

`is_low_quality` (`routing/quality.py`), the heuristic the cascade uses to
decide whether a cheap-model response is good enough or needs escalation.
Not the models themselves, not response quality in general - specifically
whether this one rule-based function's decision agrees with what a human
would actually call good or bad.

## Why hand-labeled and rule-based, not an LLM judge

Using an LLM to score responses is the more common approach for evals at
scale, and it's a reasonable choice in general - but a bad fit for *this*
specific job. This eval suite is a CI gate (M10): it needs to run on every
commit, return the same answer every time, and not cost anything or take
long enough to slow a build down. An LLM judge introduces exactly the three
things that's incompatible with - real latency, real cost per run, and
non-determinism (the same input can score differently between runs, and
LLM judges have well-documented biases of their own, like favoring longer
or more confident-sounding answers regardless of actual correctness).

A hand-labeled dataset checked against a deterministic function has the
opposite tradeoffs: it doesn't scale past what a person can label, and it
can't evaluate anything the dataset didn't anticipate. But it's free, it's
instant, and a failure is always reproducible - which is what actually
matters for something that has to be trustworthy on every single PR, not
just accurate on average.

## Why the dataset is deliberately adversarial

`dataset.py`'s 11 cases aren't a representative sample of typical traffic -
about half of them exist specifically to target `is_low_quality`'s known
weak spots (short-but-correct answers, long-but-evasive ones). That's a
deliberate choice: an eval set built only from easy, unambiguous cases
would pass at 100% and tell you nothing you didn't already know. The
measured 54.5% accuracy this produces (M10) is not "the heuristic is wrong
half the time on real traffic" - it's "the heuristic is wrong on the
specific failure modes this set was built to find." Both framings use the
same number; only one of them is honest.

## Without real production traffic

There's no way yet to measure what fraction of *real* requests would
actually need escalation - that number literally doesn't exist until real
traffic exists. What this eval measures instead is a proxy one level
removed: not "how often does the cascade escalate in production," but "how
often does the escalation decision agree with what a human would decide,"
on cases chosen by hand to probe where that agreement is most likely to
break. The `ASSUMED_HARD_REQUEST_RATE = 0.20` in `bench/cascade_cost_demo.py`
(M9) is still exactly that - an assumption, named as one - and this eval
doesn't replace it with a measured escalation rate. What it does provide is
a check on whether the *mechanism deciding* to escalate can be trusted,
which is a real and necessary thing to know even though it isn't the same
question.

## Goodhart's law risk

"When a measure becomes a target, it ceases to be a good measure." The
moment `MINIMUM_ACCURACY` in `tests/test_eval_gate.py` becomes something
people optimize against directly, there's a real risk of tuning
`is_low_quality` to pass this specific dataset rather than to genuinely
judge quality - which would make the gate pass while making the actual
heuristic worse. The defense isn't a mechanism, it's a practice: grow the
dataset from real, observed failures (below), not from staring at these 11
cases and patching around them specifically.

## Extending the dataset

The dataset should grow the same way a regression-test suite grows from
real bugs: when `is_low_quality` gets something wrong in practice - a false
escalation that cost money for no reason, or a bad answer that slipped
through - add that exact case to `dataset.py` with its correct
`actually_good` label, the same way a bug gets a regression test before
the fix, not after. That's what keeps the eval measuring reality instead
of measuring itself.