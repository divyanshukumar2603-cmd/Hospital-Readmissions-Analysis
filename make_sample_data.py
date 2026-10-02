"""
make_sample_data.py  --  STEP 0 (sample mode only)

Generates two CSV files that match the REAL CMS schema, column for column,
so the whole pipeline (clean.py -> analysis.sql -> dashboard) can run end to
end without downloading anything.

Why this exists
---------------
The real data lives on data.cms.gov (see download_real_data.py). When you are
on a machine that can reach it, run that script instead and delete these
generated files. This generator is only so the project is runnable offline and
so every cleaning decision in clean.py has something real-looking to act on.

What makes it *realistic* (not just random):
  - One row per hospital PER CONDITION (up to 6), exactly like the real HRRP
    file -- this is the multi-condition duplication clean.py has to handle.
  - Suppressed rows: when a condition has < 25 discharges, CMS blanks the
    numeric columns and writes a footnote. We reproduce that.
  - A real footnote column with CMS-style codes.
  - Star rating is driven by the same latent "quality" that drives the excess
    readmission ratio, so higher-rated hospitals readmit slightly fewer
    patients ON AVERAGE -- a genuine but noisy signal, like the real data.
  - Some hospitals appear in only one of the two files, so the join drops rows.

Run:
    python3 make_sample_data.py
Output:
    data/hrrp.csv
    data/hospitals.csv

The random seed is fixed so results are reproducible.
"""

import csv
import os
import random

random.seed(42)  # reproducible: same files every run

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

N_HOSPITALS = 3000  # roughly the real count of HRRP-eligible hospitals

# The six HRRP conditions, written exactly as CMS names the measures.
MEASURES = [
    "READM-30-AMI-HRRP",        # heart attack
    "READM-30-HF-HRRP",         # heart failure
    "READM-30-COPD-HRRP",       # COPD
    "READM-30-PN-HRRP",         # pneumonia
    "READM-30-CABG-HRRP",       # bypass surgery
    "READM-30-HIP-KNEE-HRRP",   # hip/knee replacement
]

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY",
]

OWNERSHIP = [
    ("Voluntary non-profit - Private", 0.38),
    ("Voluntary non-profit - Other", 0.06),
    ("Voluntary non-profit - Church", 0.07),
    ("Proprietary", 0.22),                      # for-profit
    ("Government - Hospital District or Authority", 0.09),
    ("Government - Local", 0.07),
    ("Government - State", 0.04),
    ("Government - Federal", 0.02),
    ("Physician", 0.03),
    ("Tribal", 0.02),
]

HOSPITAL_TYPES = ["Acute Care Hospitals", "Critical Access Hospitals"]

# CMS-style footnote codes we will actually use.
FOOTNOTE_SUPPRESSED = "5"   # "Results are not available for this reporting period."
FOOTNOTE_TOO_FEW = "1"      # "The number of cases is too small to report."


def weighted_choice(pairs):
    r = random.random()
    cum = 0.0
    for value, weight in pairs:
        cum += weight
        if r <= cum:
            return value
    return pairs[-1][0]


def make_hospitals():
    """Build the hospital master list with a latent quality score."""
    hospitals = []
    for i in range(N_HOSPITALS):
        facility_id = f"{100000 + i:06d}"  # 6-char CMS-style id, kept as text
        state = random.choice(STATES)

        # latent quality in [0,1]; higher = better hospital.
        quality = random.betavariate(5, 5)  # bell-ish, centered near 0.5

        # Star rating 1-5 derived from quality, with noise. ~8% missing.
        if random.random() < 0.08:
            star = ""  # CMS leaves this blank / "Not Available" sometimes
        else:
            noisy = quality + random.gauss(0, 0.18)
            star = min(5, max(1, int(round(1 + noisy * 4))))

        hospitals.append({
            "Facility ID": facility_id,
            "Facility Name": f"SAMPLE HOSPITAL {i + 1}",
            "State": state,
            "Hospital Type": weighted_choice([(HOSPITAL_TYPES[0], 0.82),
                                              (HOSPITAL_TYPES[1], 0.18)]),
            "Hospital Ownership": weighted_choice(OWNERSHIP),
            "Emergency Services": random.choice(["Yes", "Yes", "Yes", "No"]),
            "Hospital overall rating": star,
            "_quality": quality,  # internal, not written to CSV
        })
    return hospitals


def write_hospitals_csv(hospitals):
    """Hospital General Information file -- one row per hospital."""
    path = os.path.join(DATA, "hospitals.csv")
    cols = ["Facility ID", "Facility Name", "State", "Hospital Type",
            "Hospital Ownership", "Emergency Services",
            "Hospital overall rating"]
    # ~2% of hospitals are missing from this file (present only in HRRP),
    # so the join will drop them -- clean.py measures how many.
    present = [h for h in hospitals if random.random() > 0.02]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for h in present:
            w.writerow({c: h[c] for c in cols})
    print(f"wrote {path}  ({len(present)} rows)")


def write_hrrp_csv(hospitals):
    """
    HRRP file -- one row per hospital PER CONDITION. Columns match the real
    CMS file: Facility Name, Facility ID, State, Measure Name,
    Number of Discharges, Footnote, Excess Readmission Ratio,
    Predicted Readmission Rate, Expected Readmission Rate,
    Number of Readmissions, Start Date, End Date.
    """
    path = os.path.join(DATA, "hrrp.csv")
    cols = ["Facility Name", "Facility ID", "State", "Measure Name",
            "Number of Discharges", "Footnote", "Excess Readmission Ratio",
            "Predicted Readmission Rate", "Expected Readmission Rate",
            "Number of Readmissions", "Start Date", "End Date"]

    # ~1.5% of HRRP hospitals never appear in the hospitals file.
    hrrp_hospitals = [h for h in hospitals if random.random() > 0.015]

    rows = 0
    suppressed = 0
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for h in hrrp_hospitals:
            quality = h["_quality"]
            # each hospital reports a random subset of the 6 conditions
            for measure in random.sample(MEASURES, k=random.randint(3, 6)):
                discharges = max(0, int(random.lognormvariate(5.2, 0.9)))

                row = {
                    "Facility Name": h["Facility Name"],
                    "Facility ID": h["Facility ID"],
                    "State": h["State"],
                    "Measure Name": measure,
                    "Number of Discharges": discharges,
                    "Footnote": "",
                    "Excess Readmission Ratio": "",
                    "Predicted Readmission Rate": "",
                    "Expected Readmission Rate": "",
                    "Number of Readmissions": "",
                    "Start Date": "07/01/2020",
                    "End Date": "06/30/2023",
                }

                if discharges < 25:
                    # CMS suppresses: blanks the numbers, writes a footnote,
                    # and the ERR column literally reads "Too Few to Report".
                    row["Number of Discharges"] = "Too Few to Report"
                    row["Excess Readmission Ratio"] = "Too Few to Report"
                    row["Footnote"] = FOOTNOTE_TOO_FEW
                    suppressed += 1
                else:
                    # ERR centered near 1.0; better hospitals (high quality)
                    # sit a bit below 1.0. Spread ~0.09, clamped to a sane range.
                    err = 1.0 - (quality - 0.5) * 0.14 + random.gauss(0, 0.06)
                    err = round(min(1.40, max(0.60, err)), 4)
                    expected = round(random.uniform(0.12, 0.26), 4)
                    predicted = round(expected * err, 4)
                    readmissions = int(round(predicted * discharges))
                    row["Excess Readmission Ratio"] = err
                    row["Predicted Readmission Rate"] = predicted
                    row["Expected Readmission Rate"] = expected
                    row["Number of Readmissions"] = readmissions

                # a few rows get a generic suppression footnote with no data
                if row["Excess Readmission Ratio"] == "" and random.random() < 0.5:
                    row["Excess Readmission Ratio"] = "N/A"
                    row["Footnote"] = FOOTNOTE_SUPPRESSED

                w.writerow(row)
                rows += 1

    print(f"wrote {path}  ({rows} rows, {suppressed} suppressed 'Too Few to Report')")


def main():
    print("Generating SAMPLE data (schema matches real CMS files).")
    print("For real data instead, run: python3 download_real_data.py\n")
    hospitals = make_hospitals()
    write_hrrp_csv(hospitals)
    write_hospitals_csv(hospitals)
    print("\nDone. Next: python3 clean.py")


if __name__ == "__main__":
    main()
