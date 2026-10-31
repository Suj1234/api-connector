"""Secret vault (TRD §2): AES-GCM with one key per tenant, derived from VAULT_KEY with HKDF.

Stands in for per-tenant KMS keys. The tenant and connector are bound into each ciphertext as
associated data, so a ciphertext copied to another tenant or connector fails to decrypt.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_VERSION = "v1"
SALT = b"integration-builder/vault/v1"


class VaultError(Exception):
    pass


@dataclass(frozen=True)
class Sealed:
    ciphertext: bytes
    nonce: bytes
    key_id: str


class Vault:
    def __init__(self, master_key_b64: str | None = None) -> None:
        raw = master_key_b64 if master_key_b64 is not None else os.environ.get("VAULT_KEY", "")
        try:
            master = base64.b64decode(raw, validate=True)
        except ValueError as error:
            raise VaultError("VAULT_KEY is not valid base64") from error
        if len(master) != 32:
            raise VaultError("VAULT_KEY must be 32 random bytes, base64-encoded")
        self._master = master

    @staticmethod
    def new_master_key() -> str:
        return base64.b64encode(os.urandom(32)).decode()

    def _tenant_key(self, tenant: str) -> bytes:
        hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=SALT, info=f"tenant:{tenant}".encode())
        return hkdf.derive(self._master)

    @staticmethod
    def _aad(tenant: str, connector_id: int | str) -> bytes:
        return f"{tenant}|{connector_id}".encode()

    def seal(self, tenant: str, connector_id: int | str, secrets: dict[str, str]) -> Sealed:
        nonce = os.urandom(12)
        plaintext = json.dumps(secrets, sort_keys=True).encode()
        ciphertext = AESGCM(self._tenant_key(tenant)).encrypt(nonce, plaintext, self._aad(tenant, connector_id))
        return Sealed(ciphertext, nonce, f"{tenant}:{KEY_VERSION}")

    def open(self, tenant: str, connector_id: int | str, sealed: Sealed) -> dict[str, str]:
        if sealed.key_id != f"{tenant}:{KEY_VERSION}":
            raise VaultError("secret belongs to another tenant or key version")
        try:
            plaintext = AESGCM(self._tenant_key(tenant)).decrypt(
                sealed.nonce, sealed.ciphertext, self._aad(tenant, connector_id)
            )
        except InvalidTag as error:
            raise VaultError("secret could not be decrypted") from error
        secrets: dict[str, str] = json.loads(plaintext)
        return secrets
