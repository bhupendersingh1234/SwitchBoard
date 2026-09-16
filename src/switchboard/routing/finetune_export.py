import json
from dataclasses import dataclass


@dataclass
class CascadeRecord:
    messages: list[dict]
    response_content: str
    was_low_quality: bool


def export_training_examples(records: list[CascadeRecord]) -> list[str]:
    """Format cascade decisions as OpenAI fine-tuning JSONL, one line per example.

    Only records where the response was NOT low quality are included - the
    fine-tuned model should learn from answers that actually passed the
    quality bar, not from the ones that needed escalation. Training on a
    failure and its correction would teach the wrong lesson.
    """
    lines = []
    for record in records:
        if record.was_low_quality:
            continue
        example = {
            "messages": [
                *record.messages,
                {"role": "assistant", "content": record.response_content},
            ]
        }
        lines.append(json.dumps(example))
    return lines