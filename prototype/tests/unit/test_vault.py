from __future__ import annotations

import pytest

from app.services.vault import Sealed, Vault, VaultError

SECRETS = {"token": "very-secret-token-123"}


@pytest.fixture
def vault() -> Vault:
    return Vault(Vault.new_master_key())


def test_round_trip(vault: Vault) -> None:
    sealed = vault.seal("acme", 7, SECRETS)
    assert vault.open("acme", 7, sealed) == SECRETS
    assert b"very-secret" not in sealed.ciphertext
    assert sealed.key_id == "acme:v1"


def test_every_seal_uses_a_new_nonce(vault: Vault) -> None:
    a, b = vault.seal("acme", 7, SECRETS), vault.seal("acme", 7, SECRETS)
    assert a.nonce != b.nonce and a.ciphertext != b.ciphertext


def test_another_tenant_cannot_open_it(vault: Vault) -> None:
    sealed = vault.seal("acme", 7, SECRETS)
    with pytest.raises(VaultError):
        vault.open("globex", 7, sealed)
    # Even with the key id rewritten, Globex's derived key doesn't fit.
    with pytest.raises(VaultError):
        vault.open("globex", 7, Sealed(sealed.ciphertext, sealed.nonce, "globex:v1"))


def test_another_connector_cannot_open_it(vault: Vault) -> None:
    sealed = vault.seal("acme", 7, SECRETS)
    with pytest.raises(VaultError):
        vault.open("acme", 8, sealed)


def test_tampering_is_detected(vault: Vault) -> None:
    sealed = vault.seal("acme", 7, SECRETS)
    flipped = bytes([sealed.ciphertext[0] ^ 1]) + sealed.ciphertext[1:]
    with pytest.raises(VaultError):
        vault.open("acme", 7, Sealed(flipped, sealed.nonce, sealed.key_id))


def test_another_master_key_cannot_open_it(vault: Vault) -> None:
    sealed = vault.seal("acme", 7, SECRETS)
    with pytest.raises(VaultError):
        Vault(Vault.new_master_key()).open("acme", 7, sealed)


@pytest.mark.parametrize("bad", ["", "not base64!", "c2hvcnQ="])
def test_bad_master_key_is_refused(bad: str) -> None:
    with pytest.raises(VaultError):
        Vault(bad)
