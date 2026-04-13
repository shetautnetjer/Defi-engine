# Source Expansion Preconditions Plan

## Scope

Near-term sequencing for the market-data and chain-data surfaces that should exist before `condition/` becomes an active owner.

## Order

1. Jupiter spot quote hardening
   - keep Jupiter spot-only
   - enforce a default `2.0` second minimum live request interval
   - capture both token→USDC and USDC→token quote directions
   - record request direction, request timestamp UTC, and response latency
2. Helius discovery plus bounded chain-event projection
   - run tracked-address discovery through RPC first
   - populate `solana_address_registry` and `program_registry`
   - project enhanced transaction transfer rows into `solana_transfer_event`
   - keep websocket capture raw-first and bounded
3. Coinbase market-data ingest
   - keep a separate raw SQLite store for Coinbase payloads
   - land canonical candles, trade prints, and L2 book snapshots in the main truth DB
   - treat Coinbase as a market-data source first, not an execution venue
4. Massive historical depth
   - add Massive after the live-source seams are stable
   - route overlapping historical data into the same canonical market-data tables

## Universe Authority

The tracked mint universe is pinned to exact contracts rather than ticker search:

- `SOL` = `So11111111111111111111111111111111111111112`
- `USDC` = `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- `ZEUS` = `ZEUS1aR7aX8DFFJf5QjWj2ftDDdNTroMNGo8YoQm3Gq`
- `JUP` = `JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN`
- `BONK` = `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`
- `zBTC` = `zBTCug3er3tLyffELcvDNrKkCymbPWysGcWihESYfLg`
- `HYPE` = `98sMhvDwXj1RQi5c5Mndm3vPe9cBqPrbLaufMXFNMh5g`
- `OPENAI` = `PreweJYECqtQwBtpxHL171nL2K6umo692gTm7Q3rpgF`

## Time Rules

- use `source_event_time_utc` as the primary event clock when a provider emits one
- fall back to `captured_at_utc` only when provider event time is missing
- store `source_time_raw`, `event_date_utc`, `hour_utc`, `minute_of_day_utc`, and `weekday_utc` on event-style canonical tables
- do not rely on local wall-clock time as trading truth
