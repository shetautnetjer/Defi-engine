"""Repo-owned trader autoresearch profile loading and validation."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_PREFERRED_PROFILES_PATH = Path(".ai/profiles.toml")
_FALLBACK_PROFILES_PATH = Path("training/config/research_profiles.example.toml")
_SCHEMA_PATH = Path(".ai/schemas/profile.schema.json")

Authority = Literal["proposal_only", "shadow_only", "advisory_only", "paper_allowed"]
Status = Literal["active", "paused", "archived"]
Exploration = Literal["conservative", "balanced", "exploratory"]
CostSensitivity = Literal[
    "ultra_cost_sensitive",
    "balanced_cost",
    "aggressive_cost_tolerant",
]


class ResearchProfileMeta(BaseModel):
    version: str
    owner: str
    purpose: str
    default_authority: Authority
    default_status: Status


class ResearchProfileDefaults(BaseModel):
    authority: Authority
    status: Status
    exploration: Exploration
    cost_sensitivity: CostSensitivity
    max_concurrent_experiments: int = Field(ge=1)
    max_daily_proposals: int = Field(ge=1)
    requires_qmd_receipt: bool
    requires_sql_metrics: bool


class ResearchProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Status = "active"
    authority: Authority
    market_style: str
    time_horizon: str
    market_focus: list[str]
    cost_sensitivity: CostSensitivity
    exploration: Exploration
    preferred_sources: list[str]
    preferred_surfaces: list[str]
    preferred_features: list[str]
    preferred_labels: list[str]
    preferred_metrics: list[str]
    disfavored_conditions: list[str] = Field(default_factory=list)
    primary_objective: str
    hypothesis_templates: list[str]
    max_concurrent_experiments: int = Field(ge=1)
    max_daily_proposals: int = Field(ge=1)
    requires_qmd_receipt: bool = True
    requires_sql_metrics: bool = True


class ResearchProfileCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ResearchProfileMeta
    defaults: ResearchProfileDefaults
    profiles: dict[str, ResearchProfile]


def resolve_research_profiles_path(repo_root: Path) -> Path:
    preferred = (repo_root / _PREFERRED_PROFILES_PATH).resolve()
    if preferred.exists():
        return preferred
    fallback = (repo_root / _FALLBACK_PROFILES_PATH).resolve()
    if fallback.exists():
        return fallback
    return preferred


def resolve_research_profile_schema_path(repo_root: Path) -> Path:
    return (repo_root / _SCHEMA_PATH).resolve()


def load_research_profile_schema(repo_root: Path) -> dict[str, Any]:
    schema_path = resolve_research_profile_schema_path(repo_root)
    if not schema_path.exists():
        return {}
    try:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid research profile schema JSON at {schema_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid research profile schema payload at {schema_path}")
    return payload


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Research profile catalog not found at {path}")
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"Invalid research profile TOML at {path}") from exc


def _merge_profile_defaults(
    *,
    name: str,
    raw_profile: dict[str, Any],
    defaults: ResearchProfileDefaults,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": defaults.status,
        "authority": defaults.authority,
        "exploration": defaults.exploration,
        "cost_sensitivity": defaults.cost_sensitivity,
        "max_concurrent_experiments": defaults.max_concurrent_experiments,
        "max_daily_proposals": defaults.max_daily_proposals,
        "requires_qmd_receipt": defaults.requires_qmd_receipt,
        "requires_sql_metrics": defaults.requires_sql_metrics,
        **raw_profile,
    }


def load_research_profile_catalog(repo_root: Path) -> ResearchProfileCatalog:
    catalog_path = resolve_research_profiles_path(repo_root)
    raw_payload = _load_toml(catalog_path)
    try:
        meta = ResearchProfileMeta.model_validate(raw_payload.get("meta", {}))
        defaults = ResearchProfileDefaults.model_validate(raw_payload.get("defaults", {}))
    except ValidationError as exc:
        raise RuntimeError(f"Invalid research profile catalog header at {catalog_path}") from exc

    raw_profiles = raw_payload.get("profiles")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise RuntimeError(f"Research profile catalog at {catalog_path} has no profiles")

    profiles: dict[str, ResearchProfile] = {}
    for name, raw_profile in raw_profiles.items():
        if not isinstance(raw_profile, dict):
            raise RuntimeError(
                f"Research profile `{name}` in {catalog_path} must be a TOML table"
            )
        try:
            profiles[name] = ResearchProfile.model_validate(
                _merge_profile_defaults(
                    name=name,
                    raw_profile=raw_profile,
                    defaults=defaults,
                )
            )
        except ValidationError as exc:
            raise RuntimeError(
                f"Invalid research profile `{name}` in {catalog_path}"
            ) from exc

    return ResearchProfileCatalog(meta=meta, defaults=defaults, profiles=profiles)


def get_research_profile(profile_name: str, *, repo_root: Path) -> ResearchProfile:
    catalog = load_research_profile_catalog(repo_root)
    try:
        return catalog.profiles[profile_name]
    except KeyError as exc:
        raise RuntimeError(
            f"Unknown trader research profile `{profile_name}`. "
            f"Expected one of: {', '.join(sorted(catalog.profiles))}."
        ) from exc


def serialize_research_profile(profile: ResearchProfile) -> dict[str, Any]:
    return profile.model_dump(mode="json")


def summarize_research_profile(profile: ResearchProfile) -> dict[str, Any]:
    payload = serialize_research_profile(profile)
    payload["summary"] = (
        f"{profile.market_style} / {profile.time_horizon} focusing on "
        f"{', '.join(profile.market_focus)} with {profile.cost_sensitivity} "
        f"and {profile.exploration} exploration."
    )
    return payload
