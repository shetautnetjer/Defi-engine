# Historical Research Protocol

## Purpose

Define the default research split for future Massive-backed historical work without letting that policy drift into the runtime ingest layer.

## Default Window

- use the latest `15` full months ending on the last fully available UTC day
- use the first `12` months for development and backtest work
- use the next `3` months as blind walk-forward

## Inclusion Rule

- if an asset has less than `15` full months of usable history, exclude it from the default research set

## Intent

- keep the development window large enough to learn stable structure
- keep the blind window long enough to reveal overfit behavior
- make the time split explicit before `condition/` and strategy work begin

## Deferred Follow-Ons

- alternative rolling windows
- venue-specific historical depth exceptions
- paper-trade replay and fill-model calibration
- promotion-sensitive research policy beyond the paper-first scope
