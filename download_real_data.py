"""
download_real_data.py  --  STEP 1 (real data): fetch the actual CMS files.

Run this on any machine with normal internet (your Mac). It pulls the two
files straight from the CMS Provider Data Catalog and writes them to data/,
replacing the sample files. Then run clean.py exactly as before -- nothing
else changes.

    python3 download_real_data.py
    python3 clean.py
    python3 run_analysis.py

How it works
------------
CMS publishes each dataset with a stable dataset id. We ask the catalog's
metastore API for the dataset's current CSV "distribution" (the download URL
changes with each quarterly release, so we never hard-code it) and download it.

  Hospital Readmissions Reduction Program : dataset id 9n3s-kdb3
  Hospital General Information             : dataset id xubh-q36u

If CMS changes its API, you can always download both CSVs by hand from:
  https://data.cms.gov/provider-data/dataset/9n3s-kdb3   (save as data/hrrp.csv)
  https://data.cms.gov/provider-data/dataset/xubh-q36u   (save as data/hospitals.csv)

NOTE: this script is NOT run in the offline sample build. It uses only the
standard library so there is nothing to install.
"""

import json
import os
import ssl
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

API = "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items"

DATASETS = {
    # dataset id : local filename
    "9n3s-kdb3": "hrrp.csv",
    "xubh-q36u": "hospitals.csv",
}

# Respect a proxy if the environment sets one (harmless otherwise).
CTX = ssl.create_default_context()


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
        return json.load(r)


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, context=CTX, timeout=180) as r, \
            open(dest, "wb") as f:
        f.write(r.read())


def find_csv_url(meta):
    """Pull the first CSV downloadURL out of a dataset's metadata."""
    for dist in meta.get("distribution", []):
        data = dist.get("data", dist)
        url = data.get("downloadURL") or data.get("accessURL")
        fmt = (data.get("format") or data.get("mediaType") or "").lower()
        if url and ("csv" in fmt or url.lower().endswith(".csv")):
            return url
    # fall back to the very first downloadURL if format wasn't labelled
    for dist in meta.get("distribution", []):
        data = dist.get("data", dist)
        if data.get("downloadURL"):
            return data["downloadURL"]
    return None


def main():
    for dataset_id, filename in DATASETS.items():
        print(f"Looking up dataset {dataset_id} ...")
        try:
            meta = get_json(f"{API}/{dataset_id}?show-reference-ids")
            url = find_csv_url(meta)
            if not url:
                print(f"  ! could not find a CSV URL for {dataset_id}; "
                      f"download it by hand (see the note in this file).")
                continue
            dest = os.path.join(DATA, filename)
            print(f"  downloading -> data/{filename}")
            download(url, dest)
            size = os.path.getsize(dest)
            print(f"  done ({size:,} bytes)")
        except Exception as e:  # noqa: BLE001  (keep it simple for debugging)
            print(f"  ! failed for {dataset_id}: {e}")
            print(f"    download it by hand (see the note at the top of this "
                  f"file) and save as data/{filename}")

    print("\nIMPORTANT -- check the join key before cleaning:")
    print("  CMS has renamed the hospital id column between releases")
    print("  ('Facility ID' vs 'Provider ID'). clean.py expects 'Facility ID'.")
    print("  If your download uses a different name, rename the column in")
    print("  clean.py (the two read_csv calls) to match, or the join breaks.")
    print("\nNext: python3 clean.py")


if __name__ == "__main__":
    main()
