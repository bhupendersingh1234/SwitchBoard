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


async def test_good_cheap_response_is_returned_without_calling_expensive_model() -> None:
    wrapped = _RecordingProvider([_good_response()])
    cascade = CascadeProvider(wrapped, cheap_model="gpt-4o-mini", expensive_model="gpt-4o")

    result = await cascade.chat_completion({"messages": [{"role": "user", "content": "hi"}]})

    assert result == _good_response()
    assert wrapped.requested_models == ["gpt-4o-mini"]


async def test_bad_cheap_response_escalates_to_expensive_model() -> None:
    wrapped = _RecordingProvider([_bad_response(), _good_response()])
    cascade = CascadeProvider(wrapped, cheap_model="gpt-4o-mini", expensive_model="gpt-4o")

    result = await cascade.chat_completion({"messages": [{"role": "user", "content": "hi"}]})

    assert result == _good_response()
    assert wrapped.requested_models == ["gpt-4o-mini", "gpt-4o"]


async def test_original_payload_fields_are_preserved_only_model_is_overridden() -> None:
    wrapped = _RecordingProvider([_good_response()])
    cascade = CascadeProvider(wrapped, cheap_model="gpt-4o-mini", expensive_model="gpt-4o")
    original = {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.7}

    await cascade.chat_completion(original)

    assert original == {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.7}


async def test_non_escalated_response_has_exactly_one_leg() -> None:
    wrapped = _RecordingProvider([_good_response()])
    cascade = CascadeProvider(wrapped, cheap_model="gpt-4o-mini", expensive_model="gpt-4o")

    response, legs = await cascade.chat_completion_with_legs(
        {"messages": [{"role": "user", "content": "hi"}]}
    )

    assert response == _good_response()
    assert len(legs) == 1
    assert legs[0].model == "gpt-4o-mini"


async def test_escalated_response_has_both_legs_with_correct_models_and_usage() -> None:
    cheap = _bad_response()
    cheap["usage"] = {"prompt_tokens": 10, "completion_tokens": 2}
    expensive = _good_response()
    expensive["usage"] = {"prompt_tokens": 10, "completion_tokens": 40}
    wrapped = _RecordingProvider([cheap, expensive])
    cascade = CascadeProvider(wrapped, cheap_model="gpt-4o-mini", expensive_model="gpt-4o")

    response, legs = await cascade.chat_completion_with_legs(
        {"messages": [{"role": "user", "content": "hi"}]}
    )

    assert response == expensive
    assert len(legs) == 2
    assert legs[0].model == "gpt-4o-mini"
    assert legs[0].usage == {"prompt_tokens": 10, "completion_tokens": 2}
    assert legs[1].model == "gpt-4o"
    assert legs[1].usage == {"prompt_tokens": 10, "completion_tokens": 40}