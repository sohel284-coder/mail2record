from apps.emails.crypto import decrypt_dict, encrypt_dict


def test_round_trip():
    original = {"password": "s3cr3t", "token": "abc.def.ghi"}
    token = encrypt_dict(original)
    assert token != str(original)
    assert "s3cr3t" not in token
    assert decrypt_dict(token) == original


def test_empty_and_garbage_decrypt_to_empty_dict():
    assert decrypt_dict("") == {}
    assert decrypt_dict("not-a-real-fernet-token") == {}
    assert encrypt_dict(None) and decrypt_dict(encrypt_dict(None)) == {}
