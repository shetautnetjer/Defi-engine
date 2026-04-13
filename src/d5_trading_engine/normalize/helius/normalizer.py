"""
D5 Trading Engine — Helius Normalizer

The first non-raw Helius projection is intentionally bounded:
- tracked-address discovery populates address and program registries
- enhanced transactions populate solana_transfer_event when transfer fields exist
"""

from __future__ import annotations

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import (
    derive_event_time_fields,
    from_unix_timestamp,
    utcnow,
)
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ProgramRegistry,
    SolanaAddressRegistry,
    SolanaTransferEvent,
)

log = get_logger(__name__, normalizer="helius")


def _extract_amount_raw(transfer: dict) -> str | None:
    value = (
        transfer.get("tokenAmount")
        or transfer.get("amount")
        or transfer.get("nativeAmount")
        or transfer.get("lamports")
    )
    if value in (None, ""):
        return None
    return str(value)


def _extract_amount_float(transfer: dict) -> float | None:
    for key in ("amount", "tokenAmount"):
        value = transfer.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    native = transfer.get("nativeAmount") or transfer.get("lamports")
    if native in (None, ""):
        return None
    try:
        return float(native)
    except (TypeError, ValueError):
        return None


def _extract_decimals(transfer: dict) -> int | None:
    for key in ("decimals",):
        value = transfer.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    token_amount = transfer.get("tokenAmount")
    if isinstance(token_amount, dict):
        for key in ("decimals",):
            value = token_amount.get(key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


class HeliusNormalizer:
    """Normalize Helius discovery and enhanced transaction data."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def normalize_transactions(self, transactions: list[dict], ingest_run_id: str) -> int:
        """Project bounded transfer rows from enhanced transaction payloads."""
        if not transactions:
            return 0

        session = get_session(self.settings)
        captured_at = utcnow()
        count = 0
        try:
            for tx in transactions:
                if not isinstance(tx, dict):
                    continue

                event_time = from_unix_timestamp(tx.get("timestamp"))
                fields = derive_event_time_fields(
                    event_time,
                    captured_at,
                    (
                        str(tx.get("timestamp"))
                        if tx.get("timestamp") is not None
                        else None
                    ),
                )
                signature = tx.get("signature")
                slot = tx.get("slot")
                fee = tx.get("fee")

                token_transfers = tx.get("tokenTransfers") or []
                for transfer in token_transfers:
                    if not isinstance(transfer, dict):
                        continue
                    session.add(
                        SolanaTransferEvent(
                            ingest_run_id=ingest_run_id,
                            signature=signature,
                            slot=slot,
                            mint=transfer.get("mint"),
                            source_address=transfer.get("fromUserAccount")
                            or transfer.get("fromTokenAccount"),
                            destination_address=transfer.get("toUserAccount")
                            or transfer.get("toTokenAccount"),
                            amount_raw=_extract_amount_raw(transfer),
                            amount_float=_extract_amount_float(transfer),
                            decimals=_extract_decimals(transfer),
                            program_id=transfer.get("programId"),
                            fee_lamports=fee,
                            transfer_type="token",
                            source_event_time_utc=fields["source_event_time_utc"],
                            captured_at_utc=fields["captured_at_utc"],
                            source_time_raw=fields["source_time_raw"],
                            event_date_utc=fields["event_date_utc"],
                            hour_utc=fields["hour_utc"],
                            minute_of_day_utc=fields["minute_of_day_utc"],
                            weekday_utc=fields["weekday_utc"],
                            time_quality=fields["time_quality"],
                        )
                    )
                    count += 1

                native_transfers = tx.get("nativeTransfers") or []
                for transfer in native_transfers:
                    if not isinstance(transfer, dict):
                        continue
                    session.add(
                        SolanaTransferEvent(
                            ingest_run_id=ingest_run_id,
                            signature=signature,
                            slot=slot,
                            mint=None,
                            source_address=transfer.get("fromUserAccount"),
                            destination_address=transfer.get("toUserAccount"),
                            amount_raw=_extract_amount_raw(transfer),
                            amount_float=_extract_amount_float(transfer),
                            decimals=9,
                            program_id=transfer.get("programId"),
                            fee_lamports=fee,
                            transfer_type="native",
                            source_event_time_utc=fields["source_event_time_utc"],
                            captured_at_utc=fields["captured_at_utc"],
                            source_time_raw=fields["source_time_raw"],
                            event_date_utc=fields["event_date_utc"],
                            hour_utc=fields["hour_utc"],
                            minute_of_day_utc=fields["minute_of_day_utc"],
                            weekday_utc=fields["weekday_utc"],
                            time_quality=fields["time_quality"],
                        )
                    )
                    count += 1

            session.commit()
            log.info("normalize_transactions_complete", count=count)
            return count
        finally:
            session.close()

    def normalize_account_discovery(self, discoveries: list[dict], ingest_run_id: str) -> int:
        """Populate address and program registries from tracked-address discovery payloads."""
        if not discoveries:
            return 0

        del ingest_run_id
        session = get_session(self.settings)
        now = utcnow()
        count = 0
        try:
            for discovery in discoveries:
                if not isinstance(discovery, dict):
                    continue

                address = discovery.get("address")
                account = discovery.get("result", {}).get("value") or {}
                if not address:
                    continue

                owner_program_id = account.get("owner")
                existing_address = (
                    session.query(SolanaAddressRegistry).filter_by(address=address).first()
                )
                if existing_address:
                    existing_address.address_type = (
                        "program" if account.get("executable") else "account"
                    )
                    existing_address.is_tracked = 1
                    existing_address.updated_at = now
                else:
                    session.add(
                        SolanaAddressRegistry(
                            address=address,
                            label=discovery.get("label"),
                            address_type="program" if account.get("executable") else "account",
                            is_tracked=1,
                            created_at=now,
                            updated_at=now,
                        )
                    )

                if owner_program_id:
                    existing_program = (
                        session.query(ProgramRegistry).filter_by(program_id=owner_program_id).first()
                    )
                    if existing_program:
                        existing_program.updated_at = now
                    else:
                        session.add(
                            ProgramRegistry(
                                program_id=owner_program_id,
                                name=None,
                                description=None,
                                category="observed",
                                created_at=now,
                                updated_at=now,
                            )
                        )

                count += 1

            session.commit()
            log.info("normalize_account_discovery_complete", count=count)
            return count
        finally:
            session.close()
