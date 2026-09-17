from switchboard.routing.cascade import CascadeLeg
from switchboard.routing.replay import replay_at_min_length


def _leg(content: str, finish_reason: str, was_low_quality: bool) -> CascadeLeg:
    return CascadeLeg(
        model="gpt-4o-mini",
        usage={},
        response_content=content,
        finish_reason=finish_reason,
        was_low_quality=was_low_quality,
    )


def test_short_answer_flips_to_good_under_a_lower_threshold() -> None:
    # Originally flagged at min_length=20 (4 chars < 20). At min_length=2, it
    # would pass - this is exactly the false-positive case M10 found.
    legs = [_leg("Yes.", "stop", was_low_quality=True)]

    result = replay_at_min_length(legs, min_length=2)

    assert result.flipped_to_good == ["Yes."]
    assert result.flipped_to_bad == []
    assert result.original_low_quality_count == 1
    assert result.replayed_low_quality_count == 0


def test_long_answer_flips_to_bad_under_a_higher_threshold() -> None:
    long_content = "A reasonably detailed answer that passed the original check."
    legs = [_leg(long_content, "stop", was_low_quality=False)]

    result = replay_at_min_length(legs, min_length=1000)

    assert result.flipped_to_bad == [long_content]
    assert result.flipped_to_good == []
    assert result.original_low_quality_count == 0
    assert result.replayed_low_quality_count == 1


def test_truncated_response_stays_low_quality_regardless_of_min_length() -> None:
    # finish_reason="length" should keep this flagged no matter how low the
    # length threshold goes - this is exactly why finish_reason needed to be
    # stored, not inferred from position or left out of the replay.
    legs = [_leg("This looks complete but got cut off", "length", was_low_quality=True)]

    result = replay_at_min_length(legs, min_length=1)

    assert result.flipped_to_good == []
    assert result.replayed_low_quality_count == 1


def test_unaffected_legs_do_not_appear_in_either_flip_list() -> None:
    legs = [
        _leg("A perfectly normal, reasonably long complete answer here.", "stop", False),
        _leg("Short.", "stop", True),
    ]

    result = replay_at_min_length(legs, min_length=20)  # same as the original threshold

    assert result.flipped_to_good == []
    assert result.flipped_to_bad == []
    assert result.total_legs == 2