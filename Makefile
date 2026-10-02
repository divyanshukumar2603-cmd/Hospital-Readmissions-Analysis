# Simple pipeline. Run `make all` for the whole thing (sample data),
# or step through one target at a time to debug.

.PHONY: all sample real clean-load analyze dashboard reset help

help:
	@echo "Targets:"
	@echo "  make all        sample data -> clean -> analyze (full offline build)"
	@echo "  make sample     generate schema-accurate sample CSVs into data/"
	@echo "  make real       download the REAL CMS files into data/ (needs internet)"
	@echo "  make clean-load run clean.py  (clean + load into readmissions.db)"
	@echo "  make analyze    run analysis.sql, write exports/ and dashboard/data.js"
	@echo "  make dashboard  print how to open the dashboard"
	@echo "  make reset      delete generated db/exports/data (start fresh)"

all: sample clean-load analyze dashboard

sample:
	python3 make_sample_data.py

real:
	python3 download_real_data.py

clean-load:
	python3 clean.py

analyze:
	python3 run_analysis.py

dashboard:
	@echo "Open dashboard/index.html in a browser (double-click works)."

reset:
	rm -f readmissions.db dashboard/data.js
	rm -f exports/*.csv exports/validation_report.txt
	rm -f data/hrrp.csv data/hospitals.csv
	@echo "Clean slate. Run 'make all' to rebuild."
