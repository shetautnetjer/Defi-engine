"""Explicit policy evaluation for bounded global regime condition receipts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import orjson
import yaml
from pydantic import BaseModel, ValidationError, model_validator

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    PolicyGlobalRegimeTraceV1,
)

GLOBAL_REGIME_V1_BIAS_MAP = Path(__file__).with_name("global_regime_v1_bias_map.yaml")
_POLICY_SET_NAME = "global_regime_v1"
_REQUIRED_REGIMES = {"long_friendly", "short_friendly", "risk_off", "no_trade"}
_NO_TRADE_REGIMES = {"risk_off", "no_trade"}

PolicyState = Literal["eligible_long", "eligible_short", "no_trade"]


class GlobalRegimePolicyRule(BaseModel):
    """Typed policy rule for one semantic regime."""

    advisory_bias: str
    allow_new_long_hypotheses: bool
    allow_new_short_hypotheses: bool
    notes: str


class GlobalRegimePolicyConfig(BaseModel):
    """Typed policy config loaded from the YAML policy surface."""

    version: int
    condition_set: str
    status: str
    description: str | None = None
    regimes: dict[str, GlobalRegimePolicyRule]

    @model_validator(mode="after")
    def validate_required_regimes(self) -> GlobalRegimePolicyConfig:
        missing = sorted(_REQUIRED_REGIMES - set(self.regimes))
        if missing:
            raise ValueError(f"Policy config is missing regimes: {', '.join(missing)}")
        return self


@dataclass(frozen=True)
class LoadedPolicyConfig:
    """Validated policy config plus stable provenance."""

    config: GlobalRegimePolicyConfig
    config_hash: str
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class EvaluatedPolicyDecision:
    """Computed policy decision before persistence."""

    policy_state: PolicyState
    reason_codes: list[str]
    rule: GlobalRegimePolicyRule
    trace_payload: dict[str, object]


def load_global_regime_policy_config(policy_path: Path | None = None) -> LoadedPolicyConfig:
    """Load and validate the bounded global-regime policy config."""

    resolved_path = policy_path or GLOBAL_REGIME_V1_BIAS_MAP
    try:
        raw_text = resolved_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Policy config could not be read: {resolved_path}") from exc

    try:
        raw_payload = yaml.safe_load(raw_text)
        if not isinstance(raw_payload, dict):
            raise TypeError("Policy config must decode to a mapping.")
        config = GlobalRegimePolicyConfig.model_validate(raw_payload)
    except (TypeError, ValidationError, yaml.YAMLError) as exc:
        raise RuntimeError(f"Policy config is invalid: {resolved_path}") from exc

    return LoadedPolicyConfig(
        config=config,
        config_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        raw_payload=raw_payload,
    )


class GlobalRegimePolicyEvaluator:
    """Policy owner for translating bounded condition truth into eligibility state."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def evaluate(self, *, condition_run_id: str | None = None) -> dict[str, object]:
        """Evaluate the bounded policy surface against a condition receipt."""

        loaded_config = load_global_regime_policy_config()
        condition_run = self._select_condition_run(condition_run_id=condition_run_id)
        if condition_run.condition_set != loaded_config.config.condition_set:
            raise RuntimeError(
                "Policy config condition_set does not match the selected condition receipt."
            )
        if condition_run.status != "success":
            raise RuntimeError(
                f"Latest condition run is not successful: {condition_run.run_id} "
                f"status={condition_run.status}"
            )

        snapshot = self._load_snapshot(condition_run.run_id)
        if snapshot is None:
            raise RuntimeError(
                f"Latest successful condition run has no snapshot: {condition_run.run_id}"
            )

        decision = self._evaluate_snapshot(
            snapshot=snapshot,
            condition_run=condition_run,
            loaded_config=loaded_config,
        )
        trace_row = self._persist_trace(
            snapshot=snapshot,
            condition_run=condition_run,
            loaded_config=loaded_config,
            decision=decision,
        )

        return {
            "trace_id": trace_row.id,
            "condition_run_id": trace_row.condition_run_id,
            "condition_snapshot_id": trace_row.condition_snapshot_id,
            "source_feature_run_id": trace_row.source_feature_run_id,
            "bucket_start_utc": trace_row.bucket_start_utc.isoformat(),
            "semantic_regime": trace_row.semantic_regime,
            "policy_state": trace_row.policy_state,
            "reason_codes": decision.reason_codes,
            "config_hash": trace_row.config_hash,
            "config_version": trace_row.config_version,
            "config_status": trace_row.config_status,
        }

    def _select_condition_run(self, *, condition_run_id: str | None) -> ConditionScoringRun:
        session = get_session(self.settings)
        try:
            if condition_run_id is not None:
                run = session.query(ConditionScoringRun).filter_by(run_id=condition_run_id).first()
            else:
                run = (
                    session.query(ConditionScoringRun)
                    .order_by(
                        ConditionScoringRun.finished_at.desc(),
                        ConditionScoringRun.started_at.desc(),
                    )
                    .first()
                )
            if run is None:
                raise RuntimeError("No condition runs exist for policy evaluation.")
            return run
        finally:
            session.close()

    def _load_snapshot(self, condition_run_id: str) -> ConditionGlobalRegimeSnapshotV1 | None:
        session = get_session(self.settings)
        try:
            return (
                session.query(ConditionGlobalRegimeSnapshotV1)
                .filter_by(condition_run_id=condition_run_id)
                .order_by(ConditionGlobalRegimeSnapshotV1.created_at.desc())
                .first()
            )
        finally:
            session.close()

    def _evaluate_snapshot(
        self,
        *,
        snapshot: ConditionGlobalRegimeSnapshotV1,
        condition_run: ConditionScoringRun,
        loaded_config: LoadedPolicyConfig,
    ) -> EvaluatedPolicyDecision:
        try:
            rule = loaded_config.config.regimes[snapshot.semantic_regime]
        except KeyError as exc:
            raise RuntimeError(
                f"Policy config has no rule for semantic_regime={snapshot.semantic_regime}"
            ) from exc

        reason_codes = [f"semantic_regime:{snapshot.semantic_regime}"]
        if snapshot.blocked_flag:
            reason_codes.append("condition_blocked")
            if snapshot.blocking_reason:
                reason_codes.append(f"condition_blocking_reason:{snapshot.blocking_reason}")
            policy_state: PolicyState = "no_trade"
        elif snapshot.semantic_regime in _NO_TRADE_REGIMES:
            reason_codes.append("semantic_regime_forces_no_trade")
            policy_state = "no_trade"
        elif snapshot.semantic_regime == "long_friendly":
            if rule.allow_new_long_hypotheses:
                reason_codes.append("yaml_allows_new_long_hypotheses")
                policy_state = "eligible_long"
            else:
                reason_codes.append("yaml_disallows_new_long_hypotheses")
                policy_state = "no_trade"
        elif snapshot.semantic_regime == "short_friendly":
            if rule.allow_new_short_hypotheses:
                reason_codes.append("yaml_allows_new_short_hypotheses")
                policy_state = "eligible_short"
            else:
                reason_codes.append("yaml_disallows_new_short_hypotheses")
                policy_state = "no_trade"
        else:
            reason_codes.append("semantic_regime_unmapped")
            policy_state = "no_trade"

        trace_payload = {
            "policy_input": {
                "condition_set": loaded_config.config.condition_set,
                "version": loaded_config.config.version,
                "status": loaded_config.config.status,
                "config_hash": loaded_config.config_hash,
            },
            "condition_input": {
                "condition_run_id": condition_run.run_id,
                "condition_snapshot_id": snapshot.id,
                "source_feature_run_id": snapshot.source_feature_run_id,
                "bucket_start_utc": snapshot.bucket_start_utc.isoformat(),
                "semantic_regime": snapshot.semantic_regime,
                "confidence": snapshot.confidence,
                "blocked_flag": bool(snapshot.blocked_flag),
                "blocking_reason": snapshot.blocking_reason,
                "macro_context_state": snapshot.macro_context_state,
                "model_family": condition_run.model_family,
            },
            "selected_rule": {
                "advisory_bias": rule.advisory_bias,
                "allow_new_long_hypotheses": rule.allow_new_long_hypotheses,
                "allow_new_short_hypotheses": rule.allow_new_short_hypotheses,
                "notes": rule.notes,
            },
            "policy_state": policy_state,
            "reason_codes": reason_codes,
        }

        return EvaluatedPolicyDecision(
            policy_state=policy_state,
            reason_codes=reason_codes,
            rule=rule,
            trace_payload=trace_payload,
        )

    def _persist_trace(
        self,
        *,
        snapshot: ConditionGlobalRegimeSnapshotV1,
        condition_run: ConditionScoringRun,
        loaded_config: LoadedPolicyConfig,
        decision: EvaluatedPolicyDecision,
    ) -> PolicyGlobalRegimeTraceV1:
        session = get_session(self.settings)
        try:
            trace_row = PolicyGlobalRegimeTraceV1(
                condition_run_id=condition_run.run_id,
                condition_snapshot_id=snapshot.id,
                source_feature_run_id=snapshot.source_feature_run_id,
                bucket_start_utc=snapshot.bucket_start_utc,
                semantic_regime=snapshot.semantic_regime,
                condition_confidence=snapshot.confidence,
                macro_context_state=snapshot.macro_context_state,
                condition_blocked_flag=int(snapshot.blocked_flag or 0),
                condition_blocking_reason=snapshot.blocking_reason,
                policy_state=decision.policy_state,
                advisory_bias=decision.rule.advisory_bias,
                allow_new_long_hypotheses=int(decision.rule.allow_new_long_hypotheses),
                allow_new_short_hypotheses=int(decision.rule.allow_new_short_hypotheses),
                config_hash=loaded_config.config_hash,
                config_version=loaded_config.config.version,
                config_status=loaded_config.config.status,
                reason_codes_json=orjson.dumps(decision.reason_codes).decode(),
                trace_json=orjson.dumps(decision.trace_payload).decode(),
                created_at=utcnow(),
            )
            session.add(trace_row)
            session.commit()
            session.refresh(trace_row)
            return trace_row
        finally:
            session.close()
