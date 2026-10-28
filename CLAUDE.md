# Cash-Advance Credit Monitor — Project Spec

> Drop this file in the root of a new repo as `CLAUDE.md`. Claude Code reads it automatically at the start of every session. Work through the phases in order; each phase has acceptance criteria that must pass before moving on.

## 1. Purpose

Build a portfolio-quality, end-to-end **credit monitoring and policy-simulation toolkit** for a short-term consumer cash-advance product (think: Tilt/Empower México, Kueski Cash, Baubap). It must demonstrate, with runnable code and a live dashboard, that the author can:

1. Generate a realistic synthetic loan book and track it through vintage curves, early delinquency, and roll rates.
2. Build a **unit-economics / valuations model** that turns credit performance into per-loan and per-cohort P&L.
3. Design and read an **A/B test with guardrails** on a credit-policy change.
4. Turn a risk-model release into a **policy change**, size the impact, and monitor for drift.
5. Do all of the above with agentic AI tooling (Claude Code) as a first-class part of the workflow.

The intended reader is a Head of Credit at a fintech lender. Every chart and number should answer a question they would actually ask.

**Author:** Nathan Moneymaker · Mérida, México
**Target audience:** credit, data-science, and product leaders at digital lenders
**License:** MIT. Synthetic data only — no real borrower data anywhere in this repo, ever.

---

## 2. Product being modeled

A mobile-first cash advance in Mexico, modeled on the public shape of the category:

| Parameter | Baseline value | Notes |
|---|---|---|
| Currency | MXN | Report USD alongside at a fixed rate from `config.yaml` (default 18.5) |
| Advance size | MXN 500 – 8,000 | Progression ladder: new borrowers start low |
| Term | 14 or 30 days (single bullet payment) | Configurable |
| Pricing | Flat fee as % of principal (default 8–15%) + optional instant-transfer fee | Compute implied CAT (Mexico's annualized total cost) for transparency |
| Repayment | Auto-debit on due date; retries at +1, +3, +7 days | Retry success rates are parameters |
| Repeat behavior | Borrowers who repay on time are offered a larger advance next cycle | "Repeat-loan progression" |
| Credit decision | Score from a logistic model on cash-flow features | Replaces a bureau score; most borrowers are thin-file |

Delinquency buckets (days past due): `current`, `1–7`, `8–30`, `31–60`, `61–90`, `90+ / charge-off`. Charge-off at 90 DPD. Recoveries after charge-off are modeled as a lump recovery rate.

---

## 3. Repository layout

```
cash-advance-credit-monitor/
├── CLAUDE.md                  ← this file
├── README.md                  ← written in Phase 6; the public face of the project
├── config.yaml                ← every tunable assumption lives here, nowhere else
├── pyproject.toml             ← uv or poetry; Python 3.11+
├── data/
│   ├── raw/                   ← generated parquet files (gitignored except a small sample)
│   └── sample/                ← 5k-loan sample committed so the dashboard runs on clone
├── src/cacm/
│   ├── __init__.py
│   ├── config.py              ← loads config.yaml into a typed dataclass
│   ├── generate.py            ← synthetic borrower + loan + payment event generator
│   ├── features.py            ← cash-flow features → application score
│   ├── policy.py              ← eligibility, amount assignment, pricing, progression rules
│   ├── performance.py         ← vintage curves, DPD buckets, roll rates, early-delinquency flags
│   ├── economics.py           ← per-loan and per-cohort unit economics; valuation of a policy
│   ├── experiments.py         ← A/B assignment, power calc, guardrails, readout
│   ├── monitoring.py          ← drift detection on inputs, score, and outcomes (PSI, CSI, alerting)
│   └── dashboard.py           ← Streamlit app
├── notebooks/
│   ├── 01_explore_portfolio.ipynb
│   ├── 02_policy_change_readout.ipynb
│   └── 03_model_release_to_policy.ipynb
├── tests/                     ← pytest; every module gets tests
├── docs/
│   ├── methodology.md         ← definitions of every metric, written for a credit audience
│   └── decisions/             ← one short ADR per material modeling choice
└── Makefile                   ← make data / make test / make dashboard / make report
```

---

## 4. Phases and acceptance criteria

Work strictly in order. Commit at the end of each phase with a message that names the phase. Do not start a phase until the previous phase's tests pass.

### Phase 0 — Scaffold (30 min)
- Create the layout above, `pyproject.toml` with deps: `pandas`, `numpy`, `pyarrow`, `scipy`, `scikit-learn`, `statsmodels`, `plotly`, `streamlit`, `pyyaml`, `pytest`, `ruff`.
- `config.yaml` with every parameter in §2 and §5 as named keys with comments.
- `make test` runs and passes an empty test suite. `ruff check` passes.

**Done when:** `uv run pytest` is green on a fresh clone.

### Phase 1 — Synthetic portfolio generator (`generate.py`)
Generate 36 monthly origination cohorts (default 24 months history + 12 months forward) of borrowers, loans, and payment events.

Borrower-level latent variables (never exposed to the scorer directly):
- `true_risk` ~ Beta(a, b) — the real default propensity.
- `income_volatility`, `avg_monthly_inflow`, `inflow_regularity`, `existing_obligations_ratio`, `account_age_months`, `region` (CDMX, Jalisco, Nuevo León, Yucatán, Other), `channel` (organic, paid, referral).
- Observable cash-flow features are noisy functions of the latent variables; the noise level is a config knob so the author can show how feature quality changes outcomes.

Loan lifecycle:
- Apply → scored (Phase 2) → policy decision (Phase 3) → disbursed → due date → payment event(s) → status.
- Repeat borrowing: each on-time repayer re-applies with probability `p_repeat`; progression ladder increases amount.
- Macro shock: config flag that degrades repayment for cohorts originated in a chosen window, so drift detection has something to catch.

Output tables (parquet):
- `borrowers` (one row per borrower)
- `applications` (one row per application: features, score, decision, reason codes)
- `loans` (one row per funded loan: amount, fee, term, due date, cohort month, segment, channel)
- `payment_events` (one row per attempt: date, amount, success flag, retry index)
- `loan_status_daily` (loan × day: DPD bucket) — or a derived monthly snapshot if daily is too large

**Done when:**
- `make data` builds all tables in < 2 minutes for 200k loans.
- Tests assert: no loan repaid before disbursement, DPD monotone until a payment, charge-off only at ≥ 90 DPD, cohort default rates fall within configured ranges.
- `data/sample/` holds a committed 5k-loan subset.

### Phase 2 — Scoring (`features.py`)
- Build 8–12 interpretable cash-flow features from the observable borrower data.
- Fit a logistic regression on the first 12 cohorts; hold out the rest. Report AUC/Gini and KS on holdout, plus a score-band table (10 bands) with default rate per band.
- Export `model_v1.pkl` and a `model_card.md` (features, performance, known limitations).
- Build a deliberately better `model_v2` (adds one strong feature or uses gradient boosting) for Phase 5's model-release exercise.

**Done when:** Holdout Gini for v1 is in the 0.35–0.55 range (realistic for thin-file), v2 is measurably better, and the score-band table is monotonic.

### Phase 3 — Policy engine (`policy.py`)
Implement a `Policy` object that takes an application and returns a decision:
- **Eligibility:** score cutoff, minimum account age, minimum inflow, max obligations ratio, region/channel overrides.
- **Amount assignment:** starting amount by score band; progression ladder by repeat count and on-time history.
- **Pricing:** fee % by score band; instant-transfer fee toggle.
- **Reason codes** for every decline.

Policies are declared in YAML so the author can diff two policies and show exactly what changed.

**Done when:** Re-running the generator with a stricter policy produces a lower approval rate and a lower loss rate, and tests cover every rule.

### Phase 4 — Performance monitoring (`performance.py`)
Compute, with tests and docstrings written for a credit audience:
- **Vintage curves:** cumulative charge-off % by months-on-book, one line per origination cohort; also "cumulative 30+ DPD" as an early read.
- **Early-delinquency indicators:** first-payment default rate, 7+ DPD at day 7, 30+ DPD at day 30, by cohort and by segment.
- **Roll rates:** monthly transition matrix between DPD buckets; cure rates; roll-forward from 1–7 → 8–30 → 31–60 → 61–90 → charge-off.
- **Segment cuts:** by score band, amount tier, region, channel, repeat vs new.

**Done when:** `notebooks/01_explore_portfolio.ipynb` renders all four views with Plotly, and the macro-shock cohorts are visibly worse on the vintage chart.

### Phase 5 — Unit economics and valuation (`economics.py`)
Per-loan P&L: fee revenue + instant-transfer fee − expected loss (PD × LGD × EAD) − cost of funds (annualized rate × principal × days/365) − servicing cost − acquisition cost (new borrowers only, by channel) − collections cost. Output contribution margin, ROA, and payback.

Cohort / policy valuation:
- Aggregate per-loan P&L into cohort lifetime value including expected repeat loans (use observed repeat and progression rates).
- `value_policy(policy, portfolio)` returns NPV at a configurable discount rate, approval rate, expected loss rate, and volume.
- Sensitivity table: ±20% on fee, PD, cost of funds, repeat rate, acquisition cost → NPV change (a tornado chart).

**Done when:** The notebook shows the trade-off curve approval rate vs. NPV as the score cutoff moves, and names the cutoff that maximizes NPV subject to a loss-rate ceiling from config.

### Phase 6 — Experiments with guardrails (`experiments.py`)
- Random assignment at borrower level with a hash-based salt; stratify by score band.
- Power calculation: minimum sample size for a target lift in approval rate / loss rate at α = 0.05, power 0.8.
- Guardrails: pre-registered metrics that stop the test (e.g., 7+ DPD at day 7 exceeds control by > X pp with p < 0.05; first-payment default above a ceiling). Implement sequential checks with an alpha-spending correction (O'Brien-Fleming or a simple Bonferroni) so the author can speak to peeking.
- Readout: treatment vs. control on primary metric, guardrails, and NPV per approved borrower, with confidence intervals; a one-paragraph auto-generated decision memo.

Worked example in `notebooks/02_policy_change_readout.ipynb`: "Raise starting amount for score band 7–8 from MXN 1,000 to 1,500." Run it, show it tripped (or did not trip) a guardrail, and state the ship/no-ship decision.

**Done when:** Tests include a null A/A test that shows no significant difference, and a known-effect test that detects it at the computed sample size.

### Phase 7 — Model release → policy, and drift monitoring (`monitoring.py`)
- `notebooks/03_model_release_to_policy.ipynb`: swap `model_v1` for `model_v2`, re-map cutoffs to hold approval rate constant, size the expected loss reduction and NPV lift, and write a release/monitoring plan (what to watch, for how long, rollback trigger).
- Drift: PSI on each input feature and on the score distribution, month over month; CSI per feature; outcome drift (actual vs. expected first-payment default by cohort). Alerts fire when thresholds in config are crossed. Show the macro-shock cohort being caught.

**Done when:** The notebook prints a dated alert for the shock window and the dashboard shows it.

### Phase 8 — Dashboard (`dashboard.py`) and README
Streamlit app with five tabs: **Portfolio** (vintage + early delinquency), **Roll rates**, **Unit economics** (cohort LTV + tornado), **Experiments** (live readout of the worked example), **Drift & alerts**. Each tab has one sentence at the top saying what question it answers and what the current answer is.

README must contain: a 3-sentence pitch, a GIF or screenshots of the dashboard, "How to run" in four commands, the methodology summary with links to `docs/methodology.md`, and a "What I'd do next" section. Write it for a hiring manager, not a developer.

**Done when:** Fresh clone → `make dashboard` works on the committed sample with zero extra steps. Deploy to Streamlit Community Cloud and put the URL in the README.

---

## 5. Default assumptions (`config.yaml` seeds)

Use these as starting points; every one is a knob. Cite the source of any value you change in `docs/decisions/`.

```yaml
fx_mxn_per_usd: 18.5
cohorts: {history_months: 24, forward_months: 12, loans_per_month: 6000}
amount_ladder_mxn: [500, 1000, 1500, 2500, 4000, 6000, 8000]
fee_pct_by_band: {1: 0.15, 2: 0.14, 3: 0.13, 4: 0.12, 5: 0.11, 6: 0.10, 7: 0.09, 8: 0.09, 9: 0.08, 10: 0.08}
instant_transfer_fee_mxn: 49
instant_transfer_take_rate: 0.6
term_days_options: [14, 30]
retry_schedule_days: [1, 3, 7]
retry_success_rates: [0.35, 0.20, 0.10]
charge_off_dpd: 90
recovery_rate_post_co: 0.08
p_repeat_on_time: 0.72
cost_of_funds_annual: 0.18
servicing_cost_per_loan_mxn: 15
collections_cost_per_delinquent_loan_mxn: 60
cac_by_channel_mxn: {organic: 40, paid: 320, referral: 110}
discount_rate_annual: 0.20
loss_rate_ceiling: 0.12
macro_shock: {enabled: true, start_cohort: "2025-09", end_cohort: "2025-11", pd_multiplier: 1.5}
drift_thresholds: {psi_warn: 0.10, psi_alert: 0.25, fpd_pp_alert: 2.0}
```

---

## 6. Working rules for Claude Code

- **Read this file first** in every session; summarize which phase we are in before writing code.
- One phase per session unless told otherwise. End each session by updating `## 7. Progress log` below.
- Every metric gets a docstring in plain credit language (what it is, how it is computed, why a credit manager cares). No unexplained abbreviations.
- Tests before dashboards. Never ship a chart whose number is not covered by a test.
- Keep `config.yaml` the single source of assumptions; never hard-code a rate.
- Prefer `pandas` + `numpy`; use `polars` only if 200k loans is too slow.
- Plotly for every chart; consistent color scheme; cohort charts always have months-on-book on the x-axis.
- When a modeling choice is debatable (e.g., LGD assumption, discounting repeat loans), write a 10-line ADR in `docs/decisions/NNN-title.md` with options considered and the choice.
- Synthetic data only. If anything looks like it could be real PII, stop and delete it.
- Commit messages: `phase-N: short description`.

---

## 7. Progress log

| Date | Phase | What was done | Open issues |
|---|---|---|---|
| 2026-10-28 | 0 | Scaffold: repo layout, pyproject (uv, py3.11), config.yaml with all §2/§5 keys, config.py loader + tests, Makefile, .gitignore, ADR template. pytest + ruff green. | GitHub remote (nmakemoney) not yet added; `uv sync` to be run locally. |

---

## 8. Stretch goals (only after Phase 8 ships)

- Collections strategy simulator: retry timing and hardship-plan offers vs. cure rate and cost.
- Pricing experiment: fee % by band with a revenue-vs-approval guardrail.
- A second product (BNPL installments) sharing the same borrower base.
- Export a one-page PDF "credit committee pack" from the dashboard.
