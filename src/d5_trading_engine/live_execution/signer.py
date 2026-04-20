"""External transaction-signing boundary for Solana micro-live execution."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass

import orjson

from d5_trading_engine.config.settings import Settings


@dataclass(frozen=True)
class SignedTransaction:
    signed_transaction: str
    signer_pubkey: str


class TransactionSigner:
    """Minimal signer interface used by the Jupiter micro-live executor."""

    signer_pubkey: str = ""

    def sign(self, unsigned_transaction: str, *, request_id: str) -> SignedTransaction:
        raise NotImplementedError


class ExternalCommandSigner(TransactionSigner):
    """Delegate signing to an operator-owned command without storing key material."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.signer_pubkey = settings.micro_live_signer_pubkey

    def sign(self, unsigned_transaction: str, *, request_id: str) -> SignedTransaction:
        if not self.settings.micro_live_signer_command:
            raise RuntimeError("MICRO_LIVE_SIGNER_COMMAND is required for external signing")

        env = os.environ.copy()
        if self.settings.solana_keypair_path is not None:
            env["SOLANA_KEYPAIR_PATH"] = str(self.settings.solana_keypair_path)

        payload = {
            "unsigned_transaction": unsigned_transaction,
            "request_id": request_id,
        }
        completed = subprocess.run(
            shlex.split(self.settings.micro_live_signer_command),
            input=orjson.dumps(payload),
            capture_output=True,
            env=env,
            check=False,
            timeout=self.settings.micro_live_signer_timeout_seconds,
        )
        if completed.returncode != 0:
            raise RuntimeError("external signer command failed")

        output = orjson.loads(completed.stdout)
        signed_transaction = str(output.get("signed_transaction") or "")
        signer_pubkey = str(output.get("signer_pubkey") or self.signer_pubkey or "")
        if not signed_transaction or not signer_pubkey:
            raise RuntimeError("external signer output missing signed_transaction or signer_pubkey")

        return SignedTransaction(
            signed_transaction=signed_transaction,
            signer_pubkey=signer_pubkey,
        )

