from app.services.auth.providers import hash_password, verify_password


def test_password_hash_is_salted_and_verifiable():
    password = "a-strong-test-password"
    first = hash_password(password)
    second = hash_password(password)

    assert first != second
    assert password not in first
    assert verify_password(password, first)
    assert not verify_password("wrong-password", first)


def test_invalid_password_hash_fails_closed():
    assert not verify_password("anything", None)
    assert not verify_password("anything", "not-a-valid-hash")
