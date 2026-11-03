# analyze_unit_history.py

Run from movetest with `python -B run.py -m eda_tools.analyze_unit_history --manifest courses/AIDA-2156/data/reports/unit_history/RUN/download_manifest.json`.

Reads completed unit-value CSVs and verifies SHA-256 against both response metadata and the run manifest. Deduplicates station/time/parameter keys by latest downloaded revision. Preserves original values, source timestamps, receipt times, qualifiers, symbols, approvals and grades in a SQLite database. Counts identical repeats and conflicting revisions separately.

Writes per-station paired observation CSVs, exact-time common and screened cohorts, inferred cadence/gap records, chronological 60/20/20 candidate assignments and analysis_report.json under course data/processed/model_unit_history/RUN. Four river stations require numeric Q and level, while the lake requires level only. The screened cohort requires positive values and blank Symbol/Qualifiers condition fields. Numeric grades, Qualifier values and provisional approvals are retained for review. Observation-time candidate splits precede downstream propagation alignment and label purging. Calls project path utilities and the bilingual companion writer. Reads no daily data and starts no acquisition or training.
