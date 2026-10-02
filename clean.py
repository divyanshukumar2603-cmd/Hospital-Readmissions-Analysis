"""
clean.py  --  STEP 2: clean the raw CSVs and load them into SQLite.

This is the honest heart of the project. Every judgement call below is made
explicitly, printed, and recorded in exports/validation_report.txt so the
numbers in the README can be traced back to code.

What it does, in order:
  1. Read data/hrrp.csv and data/hospitals.csv  (IDs kept as text!).
  2. Clean the HRRP file   (suppressed values, numeric columns, condition name).
  3. Clean the hospitals file (star rating -> number).
  4. Validate: row counts, nulls, distinct hospitals, numeric ranges, join loss.
  5. Load three tables into readmissions.db:  hrrp, hospitals, joined.

Run:
    python3 clean.py
Output:
    readmissions.db
    exports/validation_report.txt

Needs: pandas  (pip install -r requirements.txt)

CLEANING DECISIONS (also in the README):
  - Facility ID is read as TEXT. Real CMS ids have leading zeros (e.g. 010001);
    reading them as numbers would silently drop the zero and break the join.
  - Suppressed values. CMS writes "Too Few to Report" / "N/A" into numeric
    columns. We convert those to NULL (not 0 -- 0 would be a lie) and keep the
    row, so the hospital still counts, but it is excluded from ratio averages
    by `WHERE ... IS NOT NULL` in the SQL.
  - Footnote column is kept. It explains WHY a value is missing; dropping it
    would throw away the reason.
  - Duplicate rows are expected: the HRRP file has one row per hospital PER
    condition. We never COUNT hospitals without DISTINCT.
  - The join is an INNER join on Facility ID. Hospitals missing from either
    file are dropped; we count and report how many before proceeding.
"""

import os
import sqlite3

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
EXPORTS = os.path.join(HERE, "exports")
DB_PATH = os.path.join(HERE, "readmissions.db")
os.makedirs(EXPORTS, exist_ok=True)

# Values CMS uses to mean "no real number here".
SUPPRESSED_TOKENS = {"Too Few to Report", "N/A", "Not Available", "", "NA"}

# Map the CMS measure code to a human condition name for charts/readability.
CONDITION_BY_MEASURE = {
    "READM-30-AMI-HRRP": "Heart Attack (AMI)",
    "READM-30-HF-HRRP": "Heart Failure",
    "READM-30-COPD-HRRP": "COPD",
    "READM-30-PN-HRRP": "Pneumonia",
    "READM-30-CABG-HRRP": "Bypass Surgery (CABG)",
    "READM-30-HIP-KNEE-HRRP": "Hip/Knee Replacement",
}

# Collect lines for the validation report as we go.
report_lines = []


def log(msg=""):
    print(msg)
    report_lines.append(str(msg))


def to_number(series):
    """Turn a messy text column into numbers; suppressed tokens become NaN."""
    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.where(~cleaned.isin(SUPPRESSED_TOKENS))
    return pd.to_numeric(cleaned, errors="coerce")


def clean_hrrp():
    path = os.path.join(DATA, "hrrp.csv")
    # dtype=str everywhere first, so leading-zero Facility IDs survive.
    df = pd.read_csv(path, dtype=str).fillna("")
    raw_rows = len(df)
    log(f"HRRP: read {raw_rows:,} raw rows from {os.path.relpath(path, HERE)}")

    df["Facility ID"] = df["Facility ID"].str.strip()
    df["condition"] = df["Measure Name"].map(CONDITION_BY_MEASURE).fillna(
        df["Measure Name"])

    # Count suppressed rows BEFORE converting, so we can report them.
    err_raw = df["Excess Readmission Ratio"].astype(str).str.strip()
    suppressed_mask = err_raw.isin(SUPPRESSED_TOKENS)
    log(f"HRRP: {suppressed_mask.sum():,} rows have a suppressed Excess "
        f"Readmission Ratio -> set to NULL (kept, not deleted)")

    # Convert the numeric columns.
    df["excess_readmission_ratio"] = to_number(df["Excess Readmission Ratio"])
    df["number_of_discharges"] = to_number(df["Number of Discharges"])
    df["predicted_readmission_rate"] = to_number(df["Predicted Readmission Rate"])
    df["expected_readmission_rate"] = to_number(df["Expected Readmission Rate"])
    df["number_of_readmissions"] = to_number(df["Number of Readmissions"])

    out = df.rename(columns={
        "Facility ID": "facility_id",
        "Facility Name": "facility_name",
        "State": "state",
        "Measure Name": "measure_name",
        "Footnote": "footnote",
    })[[
        "facility_id", "facility_name", "state", "measure_name", "condition",
        "number_of_discharges", "footnote", "excess_readmission_ratio",
        "predicted_readmission_rate", "expected_readmission_rate",
        "number_of_readmissions",
    ]]
    return out


def clean_hospitals():
    path = os.path.join(DATA, "hospitals.csv")
    df = pd.read_csv(path, dtype=str).fillna("")
    log(f"Hospitals: read {len(df):,} rows from {os.path.relpath(path, HERE)}")

    df["Facility ID"] = df["Facility ID"].str.strip()
    df["star_rating"] = to_number(df["Hospital overall rating"])
    missing_star = df["star_rating"].isna().sum()
    log(f"Hospitals: {missing_star:,} rows have no star rating -> NULL "
        f"(kept; excluded from star-rating analysis by WHERE ... IS NOT NULL)")

    out = df.rename(columns={
        "Facility ID": "facility_id",
        "Facility Name": "facility_name",
        "State": "state",
        "Hospital Type": "hospital_type",
        "Hospital Ownership": "hospital_ownership",
        "Emergency Services": "emergency_services",
    })[[
        "facility_id", "facility_name", "state", "hospital_type",
        "hospital_ownership", "emergency_services", "star_rating",
    ]]
    return out


def validate(hrrp, hospitals):
    log("\n--- VALIDATION ---")
    hrrp_ids = set(hrrp["facility_id"])
    hosp_ids = set(hospitals["facility_id"])

    log(f"Distinct hospitals in HRRP file:      {len(hrrp_ids):,}")
    log(f"Distinct hospitals in hospitals file: {len(hosp_ids):,}")

    only_hrrp = hrrp_ids - hosp_ids
    only_hosp = hosp_ids - hrrp_ids
    matched = hrrp_ids & hosp_ids
    log(f"In HRRP but NOT in hospitals file:    {len(only_hrrp):,} "
        f"(dropped by inner join)")
    log(f"In hospitals but NOT in HRRP file:    {len(only_hosp):,} "
        f"(dropped by inner join)")
    log(f"SURVIVING sample (matched hospitals): {len(matched):,}")

    err = hrrp["excess_readmission_ratio"].dropna()
    log(f"\nExcess Readmission Ratio: n={len(err):,}  "
        f"min={err.min():.4f}  max={err.max():.4f}  mean={err.mean():.4f}")
    log("  (ERR > 1.0 = worse than expected; < 1.0 = better. It is a ratio.)")

    star = hospitals["star_rating"].dropna()
    log(f"Star rating: n={len(star):,}  min={star.min():.0f}  "
        f"max={star.max():.0f}  mean={star.mean():.2f}")

    log("\nNulls per key HRRP column:")
    for c in ["excess_readmission_ratio", "number_of_discharges",
              "number_of_readmissions"]:
        log(f"  {c:28s} {hrrp[c].isna().sum():,} null of {len(hrrp):,}")


def load_sqlite(hrrp, hospitals):
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    hrrp.to_sql("hrrp", con, index=False)
    hospitals.to_sql("hospitals", con, index=False)

    # A convenience joined table so the dashboard/analysis can be simple.
    # INNER JOIN -> only hospitals present in BOTH files survive.
    con.execute("""
        CREATE TABLE joined AS
        SELECT h.facility_id, h.facility_name, h.state, h.condition,
               h.measure_name, h.number_of_discharges,
               h.excess_readmission_ratio,
               g.hospital_type, g.hospital_ownership,
               g.emergency_services, g.star_rating
        FROM hrrp h
        JOIN hospitals g ON h.facility_id = g.facility_id;
    """)
    con.commit()
    n_join = con.execute("SELECT COUNT(*) FROM joined").fetchone()[0]
    con.close()
    log(f"\nLoaded SQLite: {os.path.relpath(DB_PATH, HERE)}")
    log(f"  tables: hrrp ({len(hrrp):,} rows), "
        f"hospitals ({len(hospitals):,} rows), joined ({n_join:,} rows)")


def main():
    log("STEP 2 -- cleaning and loading\n")
    hrrp = clean_hrrp()
    hospitals = clean_hospitals()
    validate(hrrp, hospitals)
    load_sqlite(hrrp, hospitals)

    report_path = os.path.join(EXPORTS, "validation_report.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines) + "\n")
    print(f"\nValidation report written to "
          f"{os.path.relpath(report_path, HERE)}")
    print("Next: python3 run_analysis.py")


if __name__ == "__main__":
    main()
