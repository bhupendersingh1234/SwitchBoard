from switchboard.routing.quality import is_low_quality


def _response(content: str, finish_reason: str = "stop") -> dict:
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}]
    }


def test_normal_complete_response_is_not_low_quality() -> None:
    response = _response("Here is a detailed and complete answer to your question.")
    assert is_low_quality(response) is False


def test_truncated_response_is_low_quality_regardless_of_length() -> None:
    long_but_cut_off = "This looks like a full answer but it got cut off mid" * 5
    response = _response(long_but_cut_off, finish_reason="length")
    assert is_low_quality(response) is True


def test_short_response_is_low_quality_even_with_normal_finish_reason() -> None:
    response = _response("Yes.", finish_reason="stop")
    assert is_low_quality(response) is True


def test_empty_choices_is_treated_as_low_quality_not_a_crash() -> None:
    response = {"choices": []}
    assert is_low_quality(response) is True


def test_missing_message_is_treated_as_low_quality_not_a_crash() -> None:
    response = {"choices": [{"finish_reason": "stop"}]}
    assert is_low_quality(response) is True