# Source Expansion Preconditions

Active execution surface for the mint-locked universe expansion before `condition/`, `policy/`, and paper-trading logic grow.

## Goal

Turn the bootstrap ingest into a source-aware pre-conditions layer that can support later trading research without blurring runtime authority.

## This Slice Covers

- pinning the tracked Solana spot universe to exact mints for `SOL`, `USDC`, `ZEUS`, `JUP`, `BONK`, `zBTC`, `HYPE`, and `OPENAI`
- keeping Jupiter spot-only while making quote capture two-sided and rate-limited
- adding explicit UTC event-time helper fields to event-style canonical tables
- adding Helius discovery capture plus the first bounded `solana_transfer_event` projection
- hardening `helius-ws-events` as a reconnecting, heartbeat-backed raw capture lane whose notification cap excludes subscription acknowledgements
- adding Coinbase public market-data capture with a separate raw SQLite store and canonical market tables in the main truth DB
- introducing `docs/plans/` so near-term sequencing and future research policy stop living only in chat or handoff notes

## Exit Criteria

- the mint-locked universe is encoded in `config/settings.py`
- Jupiter quote capture records request direction, request time, latency, and canonical time helpers
- Helius discovery can populate `solana_address_registry` and `program_registry`
- Helius enhanced transaction capture can project transfer rows into `solana_transfer_event`
- Helius websocket capture can write raw acknowledgement and notification receipts while counting only notifications toward `HELIUS_WS_MAX_MESSAGES`
- Coinbase product, candle, trade, and L2 book captures can write raw receipts and normalized canonical rows
- the separate Coinbase raw DB path is visible in config and CLI status
- docs and validation notes reflect the new pre-conditions source surface

## Deferred On Purpose

- Jupiter perps
- live order routing or live trading
- paper fill simulation and slippage modeling
- deeper Helius program decoding beyond the bounded transfer event projection
- websocket resumability policy beyond bounded reconnect / timeout handling
- Massive historical ingest implementation
- strategy conditions, policy decisions, and promotion-sensitive research logic
