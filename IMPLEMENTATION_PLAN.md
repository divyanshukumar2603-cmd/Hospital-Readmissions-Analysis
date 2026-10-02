# Hospital Readmissions Analysis — Implementation Plan

A phased plan to deliver the project described in the PRD: analyse US CMS
Hospital Readmissions Reduction Program (HRRP) data to answer *what separates
hospitals that readmit few patients from those that get financially penalised*,
and in particular whether higher CMS star ratings predict lower readmissions.

The work is intentionally low-code: **DB Browser for SQLite** holds and queries
the data, **Tableau Public** publishes the dashboard, and **Python is optional**
(used only if a column must be transformed before loading). Each phase below
lists its goal, concrete tasks, and the exit criteria that let you move on.

---

## Guiding principles (apply in every phase)

- **Documented judgement beats a polished number.** Every cleaning decision
  goes in the README *with its reasoning*.
- **Validate before analysing.** Row counts, nulls per column, distinct
  hospital counts, and numeric ranges are recorded at each step.
- **The README carries the project.** A reviewer may spend two minutes there
  and never open the SQL.
- **End with a recommendation, not a number.** State one finding and what a
  hospital should do about it.
- **Be honest about Python.** If the GUI import did all the work, say so — do
  not claim a pipeline that was two clicks.

---

## Phase 0 — Environment & repository setup

**Goal:** a working toolchain and an empty repo scaffold.

Tasks:
- Install **DB Browser for SQLite** (sqlitebrowser.org).
- Confirm **Tableau Public** is installed and a Tableau Public account exists
  (the dashboard must publish to a public URL).
- Confirm Python 3 is available (macOS ships it) — only needed if a transform
  is required later.
- Initialise the public GitHub repo with this structure:
  ```
  /                 README.md, analysis.sql, clean.py (only if used)
  /exports          one CSV per chart
  /data             (raw CSVs — consider .gitignore if large)
  ```

**Exit criteria:** tools open, repo scaffold committed.

---

## Phase 1 — Data acquisition

**Goal:** both source files on disk, with the join key verified.

Tasks:
- Download **File 1 — HRRP readmissions and penalties** (Kaggle `cms-hrrp`,
  or direct from CMS). One row per hospital per condition (heart failure,
  pneumonia, COPD, hip/knee replacement, heart attack, CABG). Columns include
  hospital ID, name, state, measure name, number of discharges, excess
  readmission ratio, predicted and expected readmission rates.
- Download **File 2 — Hospital General Information** (CMS Provider Data
  Catalog). One row per hospital: ID, name, state, hospital type, ownership,
  emergency-services flag, overall star rating.
- **Critical check:** confirm the hospital ID column name matches across both
  files (CMS calls it Facility ID / Provider ID and has renamed it between
  releases). A mismatch here is the single most likely thing to break the join.
- Record which **year's** file was used (needed for the README limitations).

**Exit criteria:** both CSVs downloaded; join-key column identified and
confirmed to exist in both files.

---

## Phase 2 — Load into SQLite

**Goal:** both tables queryable in one database.

Tasks:
- Create a new database `readmissions.db`.
- `File → Import → Table from CSV file`: import the HRRP file as table `hrrp`.
- Repeat for Hospital General Information as table `hospitals`.
- Run the smoke test: `SELECT * FROM hrrp LIMIT 10;`
- If (and only if) a column needs transforming before it will import cleanly,
  write that step into `clean.py` and document it honestly.

**Exit criteria:** `SELECT * FROM hrrp LIMIT 10;` returns rows. Environment is
done once one query returns rows.

---

## Phase 3 — Cleaning decisions & baseline validation

**Goal:** a clean, trustworthy dataset and a written record of every judgement
call. *This is the most valuable phase of the project.*

Decisions to make and record in the README (each with reasoning + rows
affected):
- **Suppressed values.** CMS writes text like "Too Few to Report" / "N/A" into
  numeric columns, forcing them to import as text. Decide: exclude those rows
  or treat as unknown, convert the rest to numbers, and record how many rows
  were affected.
- **Footnote columns.** Decide whether CMS footnote codes are useful or noise,
  and say which.
- **Hospitals in one file but not the other.** An inner join silently drops
  them — count how many are lost before deciding, and state the surviving
  sample size.
- **Duplicate hospital rows.** HRRP has one row per hospital *per condition*
  (up to six rows per hospital). Any count of hospitals must use `DISTINCT` /
  account for this or it will be up to six times too high.
- **Excess readmission ratio direction.** Above 1.0 = worse than expected for
  that hospital's patient mix; below 1.0 = better. Confirm this before
  analysing — reading it backwards would invert every finding.

Baseline validation numbers to capture (these go in the README):
- Row counts after each step.
- Nulls per column.
- Distinct hospital count.
- Range (min/max) of each numeric column.

**Exit criteria:** numeric columns are truly numeric; sample size after the
join is known and recorded; all decisions written down with reasoning.

---

## Phase 4 — SQL analysis: the six questions

**Goal:** six queries in a single commented `analysis.sql`, each explainable
from memory. Write them in this order — each teaches what the next needs.

| # | Question | Technique |
|---|----------|-----------|
| 1 | How many hospitals, and how many rows per condition? | `COUNT`, `GROUP BY`, `DISTINCT` |
| 2 | Which conditions have the worst average readmission ratio? | `AVG`, `ORDER BY` |
| 3 | Which states perform best and worst? | `GROUP BY` + filter on sample size |
| 4 | Do bigger hospitals (more discharges) do better or worse? | `CASE WHEN` to bucket a number |
| 5 | Does ownership type matter (non-profit, for-profit, government)? | first `JOIN` between the two files |
| 6 | **Do higher-star-rated hospitals readmit fewer patients?** | `JOIN` + `GROUP BY` + handling nulls |

Notes:
- **Q6 is the headline** — it tests whether CMS's own quality rating predicts
  the outcome it is meant to capture. Whichever way it comes out, it is a
  finding.
- **Q5 is the one to practise explaining** — the first join; be able to draw on
  paper which rows match and what happens to the ones that don't.
- **Q3 caution:** states with very few hospitals produce extreme averages.
  Filter to states above a minimum hospital count and record the threshold you
  chose.

**Exit criteria:** all six queries run against `readmissions.db`, are commented
with the question each answers, and can be explained without notes.

---

## Phase 5 — Export results for the dashboard

**Goal:** CSV result sets that Tableau will read (keeps SQL visible in the repo
and the dashboard simpler to build than a live DB connection).

Tasks:
- Export each relevant query's result to a CSV in `/exports`, one per planned
  chart.
- Point Tableau at these CSVs rather than connecting it to the database.

**Exit criteria:** `/exports` contains the CSVs backing each chart.

---

## Phase 6 — Tableau Public dashboard

**Goal:** a live, public, interactive dashboard. **Not optional** — it answers
Innovaccer's most checkable requirement (hands-on visualisation experience).

Four views on one page, with a **state filter**:
1. **Readmission ratio by condition** — horizontal bar, worst at top.
2. **Readmission ratio by star rating** — the headline finding, as a bar chart.
3. **Performance by state** — a map, or bars if the map fights you.
4. **Ownership type comparison** — grouped bars.

Tasks:
- Build the four views from the `/exports` CSVs.
- Add the state filter across the page.
- Publish to Tableau Public and capture the public URL.

**Exit criteria:** dashboard is live at a public URL; URL captured for the
README and resume.

---

## Phase 7 — README (the document that gets read)

**Goal:** the README that carries the project. Structure it so a reviewer gets
the whole story in two minutes.

Required structure:
1. **The question.**
2. **Where the data came from** (and which year's file).
3. **Cleaning decisions and why** (from Phase 3, with rows affected).
4. **The findings, with numbers.**
5. **Limitations.**
6. **What a hospital should do about it** (the recommendation).

Limitations to write down explicitly (stating these is the strongest signal in
the project):
- **No causal claim** — lower readmissions at 5-star hospitals doesn't mean the
  rating caused it; both likely trace to resources, staffing, patient mix.
- **Ratio is only partly risk-adjusted** — critics argue it under-adjusts for
  how poor a hospital's patients are; safety-net hospitals may look worse than
  they perform. (One sentence.)
- **One year, one country** — it's a snapshot; name the year.
- **Hospitals dropped by the join** — state how many were lost.
- **Suppressed small hospitals** — excluding low-case hospitals biases the
  analysis toward larger hospitals; name it.

Include the **resume line** in the README:
> US Hospital Readmissions Analysis | SQL, SQLite, Tableau — Joined CMS
> readmissions and hospital quality data across 3,000+ US hospitals to test
> whether published star ratings predict readmission performance, handling
> suppressed values and multi-condition duplication, and published an
> interactive dashboard of the results.

**Exit criteria:** README covers all six sections; links the live dashboard;
states one finding with a recommendation.

---

## Phase 8 — Final assembly, QA & publish

**Goal:** a public GitHub repo where every deliverable is present and the
"done" checklist passes.

Deliverables in the repo:
- `analysis.sql` — the six queries, each commented with what it answers.
- `README.md` — the document that actually gets read.
- `/exports` — the CSV results behind each chart.
- `clean.py` — **only if** Python was genuinely used.
- A Tableau Public dashboard, linked from the README and the resume.

**Done means all five are true** (final acceptance checklist):
- [ ] Both files loaded and joined, with the surviving row count recorded.
- [ ] Every cleaning decision written down with its reasoning.
- [ ] All six queries run, and each can be explained without notes.
- [ ] The dashboard is live at a public URL.
- [ ] The README states one finding with a number and a recommendation
      attached.

**Exit criteria:** all five boxes checked; repo pushed and public.

---

## Phase → PRD day-by-day mapping

The PRD's weekend plan (~17 hours) maps onto these phases as follows:

| PRD slot | Time | Phases |
|----------|------|--------|
| Tonight | 45 min | Phase 0–2 (install, import both tables, one `SELECT`) |
| Sat morning | 4 hrs | Phase 3 + Phase 4 Q1–3 (`SELECT`/`WHERE`/`GROUP BY`/`ORDER BY`) |
| Sat evening | 4 hrs | Phase 4 Q4–6 (`JOIN`) |
| Sun morning | 3 hrs | Finalise Phase 3 validation + Phase 5 (clean queries, record numbers, export CSVs) |
| Sun afternoon | 3 hrs | Phase 6 (build & publish dashboard) |
| Sun evening | 2 hrs | Phase 7 + Phase 8 (README, push repo) |

Tonight's 45 minutes is the only hard commitment — once the data is loaded and
one query returns rows, the project exists and the rest is incremental.
