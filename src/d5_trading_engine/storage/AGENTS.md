# `storage/` Navigation

This package owns persistence boundaries.

Use it with these rules:

- canonical truth lives in SQL under `truth/`
- raw provider payload preservation belongs in raw-storage surfaces such as
  `raw_store.py`
- analytics mirrors belong under `analytics/`
- DuckDB may help analysis, but it must not replace canonical SQL truth

When adding persistence:

- put canonical tables and ORM truth in `truth/`
- preserve replayable raw payloads instead of normalizing away provider detail
- keep storage helpers ignorant of policy and runtime authority
- keep model adapters and research code from writing sidecar truth outside the
  storage contract

If a new feature needs both canonical truth and an evidence artifact, store the
truth here and let `reporting/` own the packet/QMD surface.
