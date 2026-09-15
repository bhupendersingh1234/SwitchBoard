from dataclasses import dataclass


@dataclass
class EvalCase:
    name: str
    response: dict
    actually_good: bool


def _response(content: str, finish_reason: str = "stop") -> dict:
    return {"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]}


CASES: list[EvalCase] = [
    # Clearly good: complete, reasonably detailed, normal finish reason.
    EvalCase(
        "long_complete_explanation",
        _response(
            "Photosynthesis is the process by which plants convert light energy into "
            "chemical energy, using carbon dioxide and water to produce glucose and oxygen."
        ),
        actually_good=True,
    ),
    EvalCase(
        "long_complete_howto",
        _response(
            "To reset your password: go to Settings, click Security, then Reset Password, "
            "and follow the emailed link. The link expires after 24 hours."
        ),
        actually_good=True,
    ),
    EvalCase(
        "long_complete_comparison",
        _response(
            "Lists are mutable and ordered; tuples are immutable and ordered. Use a tuple "
            "when the data shouldn't change, a list when it should."
        ),
        actually_good=True,
    ),
    # Clearly bad: truncated mid-generation. finish_reason alone should catch these.
    EvalCase(
        "truncated_by_max_tokens",
        _response(
            "The three main causes of the French Revolution were financial crisis, "
            "social inequality between the estates, and",
            finish_reason="length",
        ),
        actually_good=False,
    ),
    EvalCase(
        "truncated_mid_sentence",
        _response(
            "Step 1: preheat the oven. Step 2: mix the dry ingredients", finish_reason="length"
        ),
        actually_good=False,
    ),
    # Refused / filtered: not a length problem, a finish_reason problem.
    EvalCase(
        "content_filtered",
        _response("I can't help with that particular request.", finish_reason="content_filter"),
        actually_good=False,
    ),
    # Known weak spot: short answers that are actually complete and correct.
    # The length heuristic will flag these as low quality - that's a real false
    # positive, not a bug in the test.
    EvalCase(
        "short_correct_yesno",
        _response("Yes."),
        actually_good=True,
    ),
    EvalCase(
        "short_correct_fact",
        _response("Paris."),
        actually_good=True,
    ),
    EvalCase(
        "short_correct_count",
        _response("42."),
        actually_good=True,
    ),
    # Known weak spot: long, complete-looking responses that never actually
    # answer the question. finish_reason="stop" and plenty of length, but bad.
    EvalCase(
        "long_but_evasive",
        _response(
            "That's a really interesting question and there are many ways to think about "
            "it depending on context, perspective, and what exactly you're looking for."
        ),
        actually_good=False,
    ),
    EvalCase(
        "long_but_off_topic",
        _response(
            "Here is some general background on the history of the field, which may or "
            "may not be directly relevant to what you asked, but is worth knowing anyway."
        ),
        actually_good=False,
    ),
]