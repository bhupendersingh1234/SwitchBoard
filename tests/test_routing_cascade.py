from switchboard.providers.base import Provider
from switchboard.routing.cascade import CascadeProvider


class _RecordingProvider(Provider):
    name = "recording"

    def __init__(self, responses: list[dict]) -> None:
        self._responses = responses
        self.requested_models: list[str] = []

    async def chat_completion(self, payload: dict) -> dict:
        self.requested_models.append(payload["model"])
        return self._responses[len(self.requested_models) - 1]

    def stream_chat_completion(self, payload: dict):
        raise NotImplementedError("not exercised by these tests")

    async def aclose(self) -> None:
        pass


def _good_response() -> dict:
    return {
        "choices": [
            {
                "message": {"content": "A complete and reasonably detailed answer."},
                "finish_reason": "stop",
            }
        ]
    }


def _bad_response() -> dict:
    return {"choices": [{"message": {"content": "Yes."}, "finish_reason": "stop"}]}


async def test_first_tier_good_response_is_returned_without_calling_later_tiers() -> None:
    wrapped = _RecordingProvider([_good_response()])
    cascade = CascadeProvider(wrapped, models=["tier-cheap", "tier-mid", "tier-expensive"])

    result = await cascade.chat_completion({"messages": [{"role": "user", "content": "hi"}]})

    assert result == _good_response()
    assert wrapped.requested_models == ["tier-cheap"]


async def test_two_tier_escalation_still_works_with_the_general_constructor() -> None:
    wrapped = _RecordingProvider([_bad_response(), _good_response()])
    cascade = CascadeProvider(wrapped, models=["gpt-4o-mini", "gpt-4o"])

    result = await cascade.chat_completion({"messages": [{"role": "user", "content": "hi"}]})

    assert result == _good_response()
    assert wrapped.requested_models == ["gpt-4o-mini", "gpt-4o"]


async def test_three_tier_cascade_escalates_through_every_tier_when_all_fail_but_last() -> None:
    wrapped = _RecordingProvider([_bad_response(), _bad_response(), _good_response()])
    cascade = CascadeProvider(wrapped, models=["tier-cheap", "tier-mid", "tier-expensive"])

    result = await cascade.chat_completion({"messages": [{"role": "user", "content": "hi"}]})

    assert result == _good_response()
    assert wrapped.requested_models == ["tier-cheap", "tier-mid", "tier-expensive"]


async def test_three_tier_cascade_stops_early_at_the_middle_tier_when_it_passes() -> None:
    wrapped = _RecordingProvider([_bad_response(), _good_response()])
    cascade = CascadeProvider(wrapped, models=["tier-cheap", "tier-mid", "tier-expensive"])

    result = await cascade.chat_completion({"messages": [{"role": "user", "content": "hi"}]})

    assert result == _good_response()
    assert wrapped.requested_models == ["tier-cheap", "tier-mid"]


async def test_last_tier_response_is_returned_even_if_it_is_also_low_quality() -> None:
    # No further tier to escalate to - the last tier's answer is what gets
    # returned, good or not. Better than an error; there's nothing left to try.
    wrapped = _RecordingProvider([_bad_response(), _bad_response()])
    cascade = CascadeProvider(wrapped, models=["tier-cheap", "tier-expensive"])

    result = await cascade.chat_completion({"messages": [{"role": "user", "content": "hi"}]})

    assert result == _bad_response()
    assert wrapped.requested_models == ["tier-cheap", "tier-expensive"]


async def test_empty_model_list_is_rejected_at_construction() -> None:
    wrapped = _RecordingProvider([])
    try:
        CascadeProvider(wrapped, models=[])
        raised = False
    except ValueError:
        raised = True
    assert raised


async def test_non_escalated_response_has_exactly_one_leg() -> None:
    wrapped = _RecordingProvider([_good_response()])
    cascade = CascadeProvider(wrapped, models=["tier-cheap", "tier-expensive"])

    response, legs = await cascade.chat_completion_with_legs(
        {"messages": [{"role": "user", "content": "hi"}]}
    )

    assert response == _good_response()
    assert len(legs) == 1
    assert legs[0].model == "tier-cheap"
    assert legs[0].was_low_quality is False
    assert legs[0].response_content == "A complete and reasonably detailed answer."
    assert legs[0].finish_reason == "stop"


async def test_three_tier_escalation_produces_a_leg_per_call_with_correct_usage() -> None:
    cheap = _bad_response()
    cheap["usage"] = {"prompt_tokens": 10, "completion_tokens": 2}
    mid = _bad_response()
    mid["usage"] = {"prompt_tokens": 10, "completion_tokens": 5}
    expensive = _good_response()
    expensive["usage"] = {"prompt_tokens": 10, "completion_tokens": 40}
    wrapped = _RecordingProvider([cheap, mid, expensive])
    cascade = CascadeProvider(wrapped, models=["tier-cheap", "tier-mid", "tier-expensive"])

    response, legs = await cascade.chat_completion_with_legs(
        {"messages": [{"role": "user", "content": "hi"}]}
    )

    assert response == expensive
    assert [leg.model for leg in legs] == ["tier-cheap", "tier-mid", "tier-expensive"]
    assert [leg.usage["completion_tokens"] for leg in legs] == [2, 5, 40]
    assert [leg.was_low_quality for leg in legs] == [True, True, False]
    assert legs[-1].response_content == "A complete and reasonably detailed answer."
    assert [leg.finish_reason for leg in legs] == ["stop", "stop", "stop"]


async def test_original_payload_fields_are_preserved_only_model_is_overridden() -> None:
    wrapped = _RecordingProvider([_good_response()])
    cascade = CascadeProvider(wrapped, models=["tier-cheap", "tier-expensive"])
    original = {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.7}

    await cascade.chat_completion(original)

    assert original == {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.7}