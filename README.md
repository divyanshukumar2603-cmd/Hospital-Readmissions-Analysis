# US Hospital Readmissions Analysis

**Do hospitals with higher CMS star ratings actually readmit fewer patients?**

The US government financially penalises hospitals — up to 3% of their Medicare
payments — when too many patients come back within 30 days. It also publishes a
1–5 star quality rating for most hospitals. This project joins those two public
datasets to test a simple question: *does the star rating predict the outcome
the penalties are meant to capture?*

**Stack:** SQLite + SQL · Python (pandas) for cleaning · an interactive HTML
dashboard. ~3,000 hospitals, six medical conditions.

> **Headline finding (sample data below, see note):** readmissions fall
> steadily as star rating rises — 1-star hospitals average an Excess
> Readmission Ratio of **1.027** (worse than expected), 5-star hospitals
> **0.974** (better). A gap of about **5 percentage points**, moving in a
> straight line across all five rating levels.

---

## A note on the data in this repo

The two CSVs in `data/` are **sample data** that match the real CMS schema
exactly and reproduce its messiness, so the whole project runs offline. The
numbers quoted here come from that sample. To reproduce the analysis on the
**real** CMS data, run one command (`python3 download_real_data.py`) and the
entire pipeline re-runs unchanged — see [`data/README.md`](data/README.md).
Calling this out rather than hiding it is deliberate: honest handling of data
provenance is part of the point.

---

## How to run it

```bash
pip install -r requirements.txt   # just pandas

make all        # sample data -> clean+load -> run SQL -> build dashboard data
# then open dashboard/index.html in a browser (double-click works)
```

Or step through it to debug any single stage:

```bash
python3 make_sample_data.py   # 0. write sample CSVs to data/  (or: make real)
python3 clean.py              # 2. clean + validate + load readmissions.db
python3 run_analysis.py       # 3. run analysis.sql, write exports/ + dashboard data
```

### What each file does

| File | Role |
|------|------|
| `make_sample_data.py` | generates schema-accurate sample CSVs (offline) |
| `download_real_data.py` | pulls the real CMS files from the Provider Data Catalog |
| `clean.py` | **the cleaning decisions** — then loads `readmissions.db` |
| `analysis.sql` | the six questions, each a commented query |
| `run_analysis.py` | runs the SQL, writes `exports/*.csv` + `dashboard/data.js` |
| `dashboard/index.html` | self-contained interactive dashboard (state filter) |
| `exports/` | one CSV per chart + `validation_report.txt` |

---

## Where the data came from

- **HRRP readmissions & penalties** — one row per hospital per condition
  (heart attack, heart failure, COPD, pneumonia, bypass/CABG, hip/knee).
  [CMS Provider Data Catalog · 9n3s-kdb3](https://data.cms.gov/provider-data/dataset/9n3s-kdb3)
- **Hospital General Information** — one row per hospital, incl. ownership and
  the overall star rating.
  [CMS Provider Data Catalog · xubh-q36u](https://data.cms.gov/provider-data/dataset/xubh-q36u)

They join on **Facility ID**. The star rating lives in one file and the
readmission ratio in the other, so the headline question is impossible to
answer without the join.

**Excess Readmission Ratio (ERR)** is the core metric: a hospital's predicted
readmission rate divided by what was expected for its patient mix.
**ERR > 1.0 = worse than expected; < 1.0 = better.** It is a ratio, not a rate.

---

## Cleaning decisions (and why)

Every decision below is made in `clean.py`, printed when it runs, and saved to
`exports/validation_report.txt`.

1. **Facility ID is read as text, not a number.** Real CMS ids have leading
   zeros (e.g. `010001`); reading them as integers drops the zero and silently
   breaks the join.
2. **Suppressed values → NULL, not 0.** CMS writes `"Too Few to Report"` /
   `"N/A"` into numeric columns for hospitals with fewer than 25 cases. These
   become NULL (not zero — zero would be a false number), the row is **kept**,
   and ratio averages exclude them with `WHERE ... IS NOT NULL`.
   *Sample run: 195 HRRP rows suppressed.*
3. **The footnote column is kept.** It explains *why* a value is missing;
   discarding it throws away the reason.
4. **Duplicate rows are expected and handled.** The HRRP file has one row per
   hospital *per condition* (up to six). Hospital counts always use
   `COUNT(DISTINCT facility_id)`, never `COUNT(*)`.
5. **The join is an inner join, and the loss is measured.** Hospitals present in
   only one file are dropped — but counted first.
   *Sample run: 50 hospitals in HRRP only, 38 in the hospitals file only;
   **2,910 hospitals survive** the join.*
6. **Missing star ratings → NULL.** Unrated hospitals are excluded from the
   star analysis rather than bucketed as 0. *Sample run: 252 unrated.*

**Validation after cleaning (sample run):** ERR ranges 0.75–1.25, mean ≈ 1.0005
(correctly centred on 1.0); star rating 1–5, mean ≈ 3.03.

---

## The six questions

All six live in [`analysis.sql`](analysis.sql), in teaching order, each with a
comment saying what it answers. Results below are from the sample run.

| # | Question | Finding (sample data) |
|---|----------|-----------------------|
| 1 | How many hospitals, how many rows per condition? | ~2,200 hospitals report each of the 6 conditions; `COUNT(*)` ≈ 5× the hospital count — hence `DISTINCT`. |
| 2 | Which conditions have the worst average ratio? | All cluster near 1.0; heart attack & hip/knee are highest, COPD lowest. Differences are small. |
| 3 | Which states perform best / worst? | Clear spread once states with < 10 hospitals are filtered out. |
| 4 | Do bigger hospitals do better or worse? | Essentially flat across size bands — size is not the story. |
| 5 | Does ownership type matter? | Government/local & physician-owned slightly better; the spread is modest. |
| 6 | **Do higher-star hospitals readmit fewer?** | **Yes — a clean, monotone decline (see below).** |

### Question 6 — the headline

| Star rating | Avg ERR | Hospitals |
|:-----------:|:-------:|:---------:|
| ★ | 1.027 | 174 |
| ★★ | 1.014 | 590 |
| ★★★ | 1.001 | 1,037 |
| ★★★★ | 0.988 | 692 |
| ★★★★★ | 0.974 | 168 |

Readmission performance improves at every step up the rating scale. The rating
tracks the outcome it is meant to capture.

---

## Dashboard

An interactive dashboard is in [`dashboard/index.html`](dashboard/index.html) —
open it in any browser (no server needed). Four views, each bar diverging from
the 1.0 reference line (blue = better than expected, red = worse), with a
**state filter** that recomputes every chart:

1. Readmission ratio by star rating (the headline)
2. Readmission ratio by condition
3. Ownership type comparison
4. Performance by state

The CSVs in `exports/` are the same results, ready to drop into **Tableau
Public** if you want to publish the PRD's Tableau version — point Tableau at the
exported CSVs rather than the database, which keeps the SQL visible in the repo.

---

## Limitations

Stating these plainly is part of the analysis, not a weakness.

- **No causal claim.** 5-star hospitals readmitting fewer patients doesn't mean
  the *rating* caused it. Both are probably downstream of resources, staffing,
  and patient mix.
- **The ratio is only partly risk-adjusted.** CMS adjusts ERR for patient mix,
  but critics argue it under-adjusts for how poor a hospital's patients are, so
  safety-net hospitals may look worse than they perform.
- **One year, one country.** This is a snapshot of a US federal programme; the
  real file's reporting period is stated in the data.
- **Hospitals dropped by the join** are counted and reported, not hidden.
- **Suppressed small hospitals.** Excluding hospitals with too few cases biases
  the sample toward larger hospitals — a real limitation, named here.

---

## Recommendation

For a payer or health system acting on this: **the CMS star rating is a usable
first-pass signal for readmission risk** — low-rated hospitals in a network are
a reasonable place to target readmission-reduction programs. But because the
relationship is correlational and the ratio under-adjusts for patient poverty,
pair the rating with a look at each hospital's patient mix before acting, so
safety-net hospitals aren't penalised for the population they serve.

---

*Analysis line:* **US Hospital Readmissions Analysis** | SQL, SQLite, Tableau —
Joined CMS readmissions and hospital quality data across 3,000+ US hospitals to
test whether published star ratings predict readmission performance, handling
suppressed values and multi-condition duplication, and published an interactive
dashboard of the results.
