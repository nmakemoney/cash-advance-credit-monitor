"""Phase 0 smoke tests: the config loads and the seeds from CLAUDE.md §5 are present."""

from cacm.config import load_config


def test_config_loads():
    cfg = load_config()
    assert cfg.fx_mxn_per_usd == 18.5
    assert cfg.charge_off_dpd == 90
    assert cfg.amount_ladder_mxn[0] == 500 and cfg.amount_ladder_mxn[-1] == 8000
    assert len(cfg.fee_pct_by_band) == 10
    assert cfg.total_months == 36


def test_probabilities_are_valid():
    cfg = load_config()
    assert abs(sum(cfg.regions.values()) - 1.0) < 1e-9
    assert abs(sum(cfg.channels.values()) - 1.0) < 1e-9
    assert all(0 <= p <= 1 for p in cfg.retry_success_rates)
    assert len(cfg.retry_schedule_days) == len(cfg.retry_success_rates)
