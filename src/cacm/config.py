"""Load ``config.yaml`` into a typed configuration object.

Every tunable assumption in the project lives in ``config.yaml`` and is
accessed through :func:`load_config`. Nothing in ``src/`` hard-codes a rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


@dataclass(frozen=True)
class Config:
    """Typed view over ``config.yaml``.

    Top-level scalar keys are exposed as attributes; nested sections are kept
    as plain dicts under the same name so new keys can be added to the YAML
    without touching this class.
    """

    random_seed: int
    currency: str
    fx_mxn_per_usd: float
    cohorts: dict[str, Any]
    amount_ladder_mxn: list[int]
    amount_min_mxn: int
    amount_max_mxn: int
    term_days_options: list[int]
    term_days_weights: list[float]
    fee_pct_by_band: dict[int, float]
    instant_transfer_fee_mxn: float
    instant_transfer_take_rate: float
    retry_schedule_days: list[int]
    retry_success_rates: list[float]
    dpd_buckets: list[int]
    charge_off_dpd: int
    recovery_rate_post_co: float
    p_repeat_on_time: float
    true_risk_beta: dict[str, float]
    feature_noise_sd: float
    regions: dict[str, float]
    channels: dict[str, float]
    policy: dict[str, Any]
    cost_of_funds_annual: float
    servicing_cost_per_loan_mxn: float
    collections_cost_per_delinquent_loan_mxn: float
    cac_by_channel_mxn: dict[str, float]
    lgd: float
    discount_rate_annual: float
    loss_rate_ceiling: float
    macro_shock: dict[str, Any]
    experiments: dict[str, Any]
    drift_thresholds: dict[str, float]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def total_months(self) -> int:
        """Number of origination cohorts: history + forward."""
        return int(self.cohorts["history_months"]) + int(self.cohorts["forward_months"])


def load_config(path: str | Path | None = None) -> Config:
    """Read ``config.yaml`` (or ``path``) and return a :class:`Config`.

    Raises ``KeyError`` if a required key is missing, so a typo in the YAML
    fails loudly at startup rather than silently in a chart.
    """
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(cfg_path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    fields = {name for name in Config.__dataclass_fields__ if name != "raw"}
    missing = fields - raw.keys()
    if missing:
        raise KeyError(f"config.yaml is missing required keys: {sorted(missing)}")
    kwargs = {name: raw[name] for name in fields}
    kwargs["fee_pct_by_band"] = {int(k): float(v) for k, v in raw["fee_pct_by_band"].items()}
    return Config(raw=raw, **kwargs)
