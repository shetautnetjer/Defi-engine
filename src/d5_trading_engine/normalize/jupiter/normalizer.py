"""
D5 Trading Engine — Jupiter Normalizer

Transforms raw Jupiter API responses into canonical truth tables:
- token_registry + token_metadata_snapshot
- token_price_snapshot
- quote_snapshot
"""

from __future__ import annotations

import orjson

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import derive_event_time_fields, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    QuoteSnapshot,
    TokenMetadataSnapshot,
    TokenPriceSnapshot,
    TokenRegistry,
)

log = get_logger(__name__, normalizer="jupiter")


class JupiterNormalizer:
    """Normalize raw Jupiter data into canonical truth tables."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def normalize_tokens(self, tokens: list[dict], ingest_run_id: str) -> int:
        """Normalize token list into token_registry + token_metadata_snapshot."""
        session = get_session(self.settings)
        now = utcnow()
        count = 0

        try:
            for token in tokens:
                if not isinstance(token, dict):
                    continue
                mint = token.get("id") or token.get("address") or token.get("mint")
                if not mint:
                    continue

                logo_uri = token.get("logoURI") or token.get("icon")
                daily_volume = token.get("daily_volume") or token.get("dailyVolume")
                existing = session.query(TokenRegistry).filter_by(mint=mint).first()
                if existing:
                    existing.symbol = token.get("symbol", existing.symbol)
                    existing.name = token.get("name", existing.name)
                    existing.decimals = token.get("decimals", existing.decimals)
                    existing.logo_uri = logo_uri or existing.logo_uri
                    existing.tags = (
                        orjson.dumps(token.get("tags", [])).decode()
                        if token.get("tags")
                        else existing.tags
                    )
                    existing.updated_at = now
                else:
                    session.add(
                        TokenRegistry(
                            mint=mint,
                            symbol=token.get("symbol"),
                            name=token.get("name"),
                            decimals=token.get("decimals"),
                            logo_uri=logo_uri,
                            tags=(
                                orjson.dumps(token.get("tags", [])).decode()
                                if token.get("tags")
                                else None
                            ),
                            provider="jupiter",
                            first_seen_at=now,
                            updated_at=now,
                        )
                    )

                session.add(
                    TokenMetadataSnapshot(
                        ingest_run_id=ingest_run_id,
                        mint=mint,
                        symbol=token.get("symbol"),
                        name=token.get("name"),
                        decimals=token.get("decimals"),
                        daily_volume=daily_volume,
                        freeze_authority=token.get("freeze_authority"),
                        mint_authority=token.get("mint_authority"),
                        metadata_json=orjson.dumps(token).decode(),
                        provider="jupiter",
                        captured_at=now,
                    )
                )
                count += 1

            session.commit()
            log.info("normalize_tokens_complete", count=count)
        finally:
            session.close()

        return count

    def normalize_prices(self, price_data: dict, ingest_run_id: str) -> int:
        """Normalize Jupiter price responses into token_price_snapshot."""
        session = get_session(self.settings)
        now = utcnow()
        count = 0

        try:
            data = price_data.get("data", price_data)
            if not isinstance(data, dict):
                return 0

            for mint, info in data.items():
                if not isinstance(info, dict):
                    continue
                price = info.get("price")
                if price is None:
                    price = info.get("usdPrice")
                if price is None:
                    continue

                session.add(
                    TokenPriceSnapshot(
                        ingest_run_id=ingest_run_id,
                        mint=mint,
                        symbol=info.get("mintSymbol"),
                        price_usd=float(price),
                        provider="jupiter",
                        captured_at=now,
                    )
                )
                count += 1

            session.commit()
            log.info("normalize_prices_complete", count=count)
        finally:
            session.close()

        return count

    def normalize_quote(
        self,
        quote_data: dict,
        ingest_run_id: str,
        *,
        request_direction: str | None = None,
        requested_at=None,
        response_latency_ms: float | None = None,
        captured_at=None,
    ) -> int:
        """Normalize a single Jupiter quote into quote_snapshot."""
        session = get_session(self.settings)
        captured = captured_at or utcnow()
        fields = derive_event_time_fields(None, captured, None)

        try:
            session.add(
                QuoteSnapshot(
                    ingest_run_id=ingest_run_id,
                    input_mint=quote_data.get("inputMint", ""),
                    output_mint=quote_data.get("outputMint", ""),
                    input_amount=str(quote_data.get("inAmount", "")),
                    output_amount=str(quote_data.get("outAmount", "")),
                    price_impact_pct=(
                        float(quote_data["priceImpactPct"])
                        if quote_data.get("priceImpactPct") not in (None, "")
                        else None
                    ),
                    slippage_bps=quote_data.get("slippageBps"),
                    route_plan_json=orjson.dumps(quote_data.get("routePlan", [])).decode(),
                    other_amount_threshold=str(quote_data.get("otherAmountThreshold", "")),
                    swap_mode=quote_data.get("swapMode"),
                    request_direction=request_direction,
                    requested_at=requested_at,
                    response_latency_ms=response_latency_ms,
                    source_event_time_utc=fields["source_event_time_utc"],
                    source_time_raw=fields["source_time_raw"],
                    event_date_utc=fields["event_date_utc"],
                    hour_utc=fields["hour_utc"],
                    minute_of_day_utc=fields["minute_of_day_utc"],
                    weekday_utc=fields["weekday_utc"],
                    time_quality=fields["time_quality"],
                    provider="jupiter",
                    captured_at=fields["captured_at_utc"],
                )
            )
            session.commit()
            return 1
        finally:
            session.close()
