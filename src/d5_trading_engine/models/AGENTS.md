# `models/` Navigation

This package holds reusable model helpers and adapters, not runtime authority.

Use it with these boundaries:

- runtime-adjacent helpers should stay thin and swappable
- shadow-only helpers must remain advisory until another owner promotes them
- optional dependencies must fail closed and degrade clearly

Current model intent:

- HMM and related regime helpers support the condition layer
- Random Forest, XGBoost, and Isolation Forest support bounded research and
  challenger work
- Chronos and other richer models remain shadow-only until explicitly widened

Model code here should:

- return metrics, metadata, and artifacts
- avoid writing canonical truth directly
- avoid owning promotion, risk, or policy decisions

Persistence belongs in `storage/`. Evidence packet writing belongs in
`reporting/`. Runtime gating belongs in the owning layer, not in model helpers.
