from switchboard.auth.keys import generate_api_key, verify_api_key


def test_generate_api_key_has_expected_prefix() -> None:
    generated = generate_api_key()
    assert generated.key.startswith("sbk_")
    assert generated.key_prefix == generated.key[:8]
    assert len(generated.key_prefix) == 8


def test_verify_api_key_accepts_correct_key() -> None:
    generated = generate_api_key()
    assert verify_api_key(generated.key, generated.key_hash) is True


def test_verify_api_key_rejects_wrong_key() -> None:
    generated = generate_api_key()
    other = generate_api_key()
    assert verify_api_key(other.key, generated.key_hash) is False


def test_generate_api_key_produces_unique_keys() -> None:
    first = generate_api_key()
    second = generate_api_key()
    assert first.key != second.key
    assert first.key_hash != second.key_hash