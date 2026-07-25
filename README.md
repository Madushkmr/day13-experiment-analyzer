# Day 13 — A/B Test & Experimentation Analyzer

Day 13 of a daily AI-app series (BI focus). This is a statistics-focused BI tool: a Flask REST API + dashboard that analyzes A/B test results using three complementary methods — a frequentist significance test, a Bayesian posterior-decision model, and an always-valid sequential test — persisted to SQLite.

## Why this matters for BI work

Every BI team eventually runs experiments (pricing changes, UI variants, feature rollouts) and needs to answer "did it work, and can we stop looking yet?" Fixed-horizon significance testing alone is a common trap: peeking at results daily before a pre-committed sample size inflates false-positive rates. This tool packages three angles analysts actually use in practice:

- **Frequentist (two-proportion z-test / Welch's t-test)** — the standard significance test stakeholders expect to see, with a p-value and confidence interval.
- **Bayesian (Beta-Binomial)** — gives a directly interpretable "probability treatment is better" plus expected-loss-based ship/keep recommendation, which is often easier to explain to non-technical stakeholders than a p-value.
- **Sequential (mSPRT, always-valid)** — a mixture-based sequential probability ratio test that stays statistically valid even when the dashboard is checked every day, so teams can stop experiments early without inflating error rates.

## Complexity tier

Multi-component app: Flask REST API + server-rendered dashboard (Chart.js), SQLite persistence, a CSV ingestion pipeline, three independent statistics modules, a pytest suite covering both the stats logic and the API layer, and a Dockerfile for deployment. This is a step up from Day 12's workflow orchestration engine by combining three distinct statistical/AI techniques behind one API rather than one execution model.

## Architecture

```
day13-experiment-analyzer/
├── app.py                    # Flask app: REST API + dashboard route
├── seed.py                   # one-shot script to load sample_data into SQLite
├── src/
│   ├── db.py                 # SQLite schema + CRUD (experiments, observations)
│   ├── ingest.py             # CSV -> SQLite loader
│   ├── stats_frequentist.py  # two-proportion z-test, Welch's t-test
│   ├── stats_bayesian.py     # Beta-Binomial posterior, expected loss, recommendation
│   └── stats_sequential.py   # mSPRT always-valid sequential test
├── templates/
│   └── dashboard.html        # dark-mode dashboard, Chart.js sequential-LR plot
├── sample_data/
│   └── experiments_daily.csv # 3 synthetic experiments, 152 daily rows
├── tests/
│   ├── test_stats.py         # unit tests for all three stats modules
│   └── test_api.py           # Flask test-client tests for the REST API
├── requirements.txt
└── Dockerfile
```

Data flows: CSV (or POST /api/experiments/<id>/observations) → SQLite `observations` table → `_build_analysis()` in `app.py` aggregates totals per variant and calls all three stats modules → JSON report / dashboard.

### Sample dataset

`sample_data/experiments_daily.csv` contains three synthetic experiments generated with a fixed random seed:

| experiment | metric | true effect |
|---|---|---|
| `checkout_button_color` | conversion | treatment +18% relative lift (clear winner) |
| `pricing_page_layout` | conversion | +1% (effectively no real effect — inconclusive) |
| `premium_upsell_banner` | revenue/user | treatment +9% relative lift |

## Running it

```bash
cd day13-experiment-analyzer
pip install -r requirements.txt

python seed.py        # loads sample_data/experiments_daily.csv into SQLite
python app.py          # starts the dashboard on http://localhost:5000
```

Then open http://localhost:5000 — pick an experiment on the left to see the frequentist/Bayesian/sequential report and the sequential-test likelihood-ratio chart.

### REST API examples

```bash
# Create an experiment
curl -X POST localhost:5000/api/experiments \
  -H 'Content-Type: application/json' \
  -d '{"name": "new_test", "metric_type": "conversion"}'

# Record a day of data
curl -X POST localhost:5000/api/experiments/1/observations \
  -H 'Content-Type: application/json' \
  -d '{"variant": "treatment", "day": 1, "users": 500, "conversions": 40}'

# Get the combined analysis
curl localhost:5000/api/experiments/1/analysis
```

### Tests

```bash
pytest tests/ -v
```

### Docker

```bash
docker build -t experiment-analyzer .
docker run -p 5000:5000 experiment-analyzer
```

## Notes / limitations

- The Welch's t-test for revenue metrics treats each day's revenue-per-user as one sample point (a practical approximation given only daily aggregates are persisted, not raw per-user rows).
- The mSPRT implementation uses a single fixed mixture variance (`tau`) rather than a fully adaptive design — sufficient for illustrating always-valid inference without the complexity of a production experimentation platform.
- This is a demo/portfolio project with synthetic data, not a production experimentation system.
