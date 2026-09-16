import json

from switchboard.routing.finetune_export import CascadeRecord, export_training_examples


def test_low_quality_records_are_excluded() -> None:
    records = [
        CascadeRecord(
            messages=[{"role": "user", "content": "good one"}],
            response_content="a complete answer",
            was_low_quality=False,
        ),
        CascadeRecord(
            messages=[{"role": "user", "content": "bad one"}],
            response_content="Yes.",
            was_low_quality=True,
        ),
    ]

    lines = export_training_examples(records)

    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["messages"][0]["content"] == "good one"


def test_output_matches_openai_fine_tuning_message_schema() -> None:
    records = [
        CascadeRecord(
            messages=[
                {"role": "system", "content": "You are concise."},
                {"role": "user", "content": "What is 2+2?"},
            ],
            response_content="4",
            was_low_quality=False,
        )
    ]

    lines = export_training_examples(records)
    parsed = json.loads(lines[0])

    assert set(parsed.keys()) == {"messages"}
    assert parsed["messages"] == [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
    ]


def test_original_messages_list_is_not_mutated() -> None:
    original_messages = [{"role": "user", "content": "hi"}]
    record = CascadeRecord(
        messages=original_messages, response_content="hello", was_low_quality=False
    )

    export_training_examples([record])

    assert original_messages == [{"role": "user", "content": "hi"}]


def test_empty_input_produces_empty_output() -> None:
    assert export_training_examples([]) == []


def test_each_line_is_independently_valid_json() -> None:
    records = [
        CascadeRecord(
            messages=[{"role": "user", "content": f"q{i}"}],
            response_content=f"a{i}",
            was_low_quality=False,
        )
        for i in range(3)
    ]

    lines = export_training_examples(records)

    assert len(lines) == 3
    for line in lines:
        json.loads(line)  # raises if malformed