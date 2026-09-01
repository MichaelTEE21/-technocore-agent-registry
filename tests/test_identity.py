import pytest

from tar.identity import DidKeyIdentityProvider, IdentityError, default_identity_provider


def test_did_key_accepts_public_identifier():
    did = "did:key:z6MkpTHR8VHsEx1K2nZ2VqKqQqQqQqQqQqQqQqQqQqQqQqQ"
    # 32+ base58 chars after z
    did = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"
    assert DidKeyIdentityProvider().validate_public_did(did) == did


def test_did_key_rejects_key_material():
    provider = DidKeyIdentityProvider()
    with pytest.raises(IdentityError):
        provider.validate_public_did("did:key:z-----BEGIN PRIVATE KEY-----abc")
    with pytest.raises(IdentityError):
        provider.validate_public_did("not-a-did")
    with pytest.raises(IdentityError):
        provider.validate_public_did("did:example:test-research")


def test_composite_accepts_example_and_key():
    assert default_identity_provider.validate_public_did("did:example:test-research")
    assert default_identity_provider.validate_public_did(
        "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"
    )


def test_composite_rejects_pem_and_private_paste():
    with pytest.raises(IdentityError):
        default_identity_provider.validate_public_did(
            "-----BEGIN PRIVATE KEY-----\nMIGH\n-----END PRIVATE KEY-----"
        )
    with pytest.raises(IdentityError):
        default_identity_provider.validate_public_did("private")
    with pytest.raises(IdentityError):
        default_identity_provider.validate_public_did("not-a-did")
