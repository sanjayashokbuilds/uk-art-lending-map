# Cancer Clock

**See where NHS cancer waits are heading, hospital by hospital, and what would help.**

Built for OxHack 2026 by Completa.

[![Watch the Cancer Clock demo](https://img.youtube.com/vi/L5Cd3Bld5f8/maxresdefault.jpg)](https://youtu.be/L5Cd3Bld5f8)

▶ **[Watch the 3-minute demo on YouTube](https://youtu.be/L5Cd3Bld5f8)**

---

## The problem

After an urgent cancer referral in England, treatment should start within **62 days**.
The target is 85% of patients; the latest reported figure is **71.9%** (August 2026),
and the target has not been met since **December 2015**. In the week ending
30 August 2026, **17,841 people** in England were still waiting past day 62.

Those figures are published about **seven weeks late**. They show where waits were,
not where they are heading, and not what would bring them down.

## What Cancer Clock does

For each of **130 NHS trusts** that treat cancer, it answers three questions:

1. **Where are waits building?** A map of England showing whether each trust's
   62-day backlog is expected to rise, fall or stay the same.
2. **What happens next?** A forecast 4, 8 and 12 weeks ahead, with an 80% range.
3. **What would help?** The likely pressure point (diagnosis or treatment) and a
   recovery planner that tests extra capacity, strikes, winter pressure and
   referral surges.

### Example: Oxford University Hospitals

| | |
| --- | --- |
| Last reported backlog | 179 (week ending 30 Aug 2026) |
| 12-week forecast | **~175** by 10 Jan 2027 (80% range 113–253) |
| Likely pressure point | **Treatment**: radiotherapy within 31 days 61.7% vs 88.7% in England |
| +10% treatment capacity from week 4 | **175 → 147**, about **28 fewer** people waiting past day 62 |
| Marginal effect near 0–5% | about **2.8 fewer** people per extra 1% of treatment capacity |

Plans are model estimates for comparing options, not guarantees.

## How it works

**Data.** Three public NHS England datasets (Open Government Licence v3.0): the weekly
62-day backlog per trust, monthly Cancer Waiting Times (28-day diagnosis by cancer type,
31-day treatment by modality) and monthly diagnostic waiting times (DM01). Each row
carries an estimated first-publication date (month + 2, day 14) so back-tests only use
data that would have been public. Four trust mergers are harmonised
(RVJ→RA7, RAP→RAL, RY2→RWW, RVY→RBN).

**Forecast.** One global LightGBM model trained across all trusts on 64 features
(backlog level and trends, diagnosis and treatment performance, diagnostic queues,
the England trend, strike days, seasonality). It predicts the log ratio of future to
current backlog, with 10th/50th/90th percentile models giving the 80% range. The
published forecast is a 50:50 blend of the model and the latest reported value.
Horizons are counted from the issue date (18 Oct 2026), so they sit 11, 15 and 19
weeks after the latest observation.

**Pressure point.** A side (diagnosis or treatment) is flagged only if it is worse
than England in at least 2 of the last 3 months, still worse after shrinking small
samples towards the national rate, and at least 5 percentage points behind.
DM01 is context only and never decides the label.

**Recovery planner.** A daily, age-structured two-stage queue (diagnosis, then
treatment) calibrated to each trust's history, with 256 Monte Carlo runs per plan.
The forecast supplies the level and paired simulations supply the change:

```
plan = forecast − simulated effect      (Oxford: 175 − 28 = 147)
```

With no changes selected, the plan exactly matches the forecast. Plans are available
for **109 of 130** trusts; the rest are withheld where inputs are missing, the fit is
poor or the history cannot separate diagnosis and treatment effects.

## Forecast evidence

Walk-forward back-test over **35 issue dates**, using only data published by each date:
**12,339** scored forecasts (4,371 / 4,113 / 3,855).

| Mean absolute error, patients | +4 weeks | +8 weeks | +12 weeks |
| --- | ---: | ---: | ---: |
| Last value ("nothing changes") | 30.25 | 32.32 | 34.30 |
| Raw LightGBM | 28.37 | 31.35 | 32.88 |
| **Selected 50:50 blend** | **28.33** | **30.63** | **32.14** |
| 80% range coverage (blend) | 84.8% | 84.1% | 83.5% |

- The blend was **selected after reviewing this back-test**, so its results are not
  independent validation.
- Raw LightGBM trust-cluster bootstrap (10,000 draws) 95% gain intervals:
  **3.8–8.5% / −0.4–6.3% / 0.1–8.0%**. The 8-week interval includes zero.
- On large swings (>30% change), raw LightGBM improves on the last value by
  13.3% / 11.8% / 14.5%; the blend by 6.7% / 6.1% / 7.5%.

## Limitations

- Uses aggregate public data, not patient records. It does not predict any individual's wait.
- Data are the latest revised values; historical first-release versions are approximated, not verified.
- Merger harmonisation uses later organisational knowledge.
- The pressure point shows where delays are, not why.
- The planner changes the whole treatment stage, not a specific modality's staffing.
  The plan range covers the simulated change only, not forecast uncertainty.
- Clinical review of the bottleneck examples is pending.

## Run it locally

Python 3.11+. The compiled frontend and precomputed results are bundled, so Node and
API keys are not needed.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q -W error
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** (API docs at `/docs`). On a Mac, LightGBM needs
`brew install libomp`. On Windows use `.venv\Scripts\python.exe`.

To serve the bundled app only, install `requirements-web.txt` instead
([deployment settings](docs/deploy.md)). For frontend changes: `cd web`, `npm ci`,
`npm run build`.

## Tech stack

Python · pandas · NumPy · SciPy · LightGBM · PyArrow · FastAPI · React · TypeScript · Vite

## Further documentation

[Forecast method](docs/methodology.md) ·
[Uncertainty](docs/uncertainty.md) ·
[Bottleneck method](docs/bottleneck_method.md) ·
[Bottleneck examples](docs/bottleneck_examples.md) ·
[Simulator method](docs/simulator_method.md) ·
[Recovery plan method](docs/recovery_plan_method.md) ·
[Assumptions](docs/assumptions.md) ·
[Data dictionary](docs/data_dictionary.md) ·
[Interface sources](docs/ui_sources.md)

## Licence and sources

Code: MIT. NHS data: [NHS England statistics](https://www.england.nhs.uk/statistics/statistical-work-areas/cancer-waiting-times/),
Open Government Licence v3.0. Source URLs and hashes are in
[docs/source_manifest.csv](docs/source_manifest.csv).

Cancer Clock is an independent tool and not an NHS product.

*Made by Completa.*
