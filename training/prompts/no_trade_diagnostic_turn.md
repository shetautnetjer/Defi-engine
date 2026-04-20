# No-Trade Diagnostic Turn

Goal: explain why a run/window produced too few or zero trades.

Required questions:
- Was raw data present?
- Was SQL coverage present?
- Were feature rows present?
- Were conditions valid?
- Did strategies create candidates?
- Did policy allow candidates?
- Did risk approve candidates?
- Were quotes/fills available?
- Did settlement finish?

Return:
- funnel counts
- primary failure surface
- top reason codes
- recommended next bounded experiment

Do not:
- loosen risk
- change strategy thresholds
- change policy
- promote anything
