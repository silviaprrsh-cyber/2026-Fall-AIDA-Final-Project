"""Build and verify the portable clean AIDA 2156 EDA submission ZIP using Python 3.13 stdlib only.

Usage (from repository root):
  python -B -E -S courses/AIDA-2156/analysis/build_and_verify_release_zip.py
"""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")


def sanitize_zip_md(rel_path: str, text: str, members: set[str]) -> str:
    dirs: set[str] = set()
    for m in members:
        parts = m.split("/")
        for k in range(1, len(parts)):
            dirs.add("/".join(parts[:k]))
    base = posixpath.dirname(rel_path)

    def repl(match: re.Match[str]) -> str:
        label, raw = match.group(1), match.group(2).strip()
        if raw.startswith(("http://", "https://", "#", "mailto:")):
            return match.group(0)
        tgt = urllib.parse.unquote(raw.split("#")[0]).rstrip("/")
        if not tgt:
            return match.group(0)
        norm = posixpath.normpath(posixpath.join(base, tgt)) if base else posixpath.normpath(tgt)
        if norm in members or norm in dirs:
            return match.group(0)
        return f"{label} (`{raw}` — see full repository; omitted from standalone ZIP)"

    return MD_LINK_RE.sub(repl, text)

WORKSPACE = Path(__file__).resolve().parents[3]
COURSE_DIR = WORKSPACE / "courses" / "AIDA-2156"
MANIFEST_PATH = COURSE_DIR / "submission-manifest.txt"
OUT_DIR = COURSE_DIR / "data" / "processed" / "eda_release_20261123"
ZIP_PATH = OUT_DIR / "AIDA2156_EDA_D2L_ready_20261123.zip"
AUDIT_JSON = COURSE_DIR / "output" / "zip-extraction-validation.json"

FROZEN_SEVEN = [
    "output/final_eda/coverage.csv",
    "output/final_eda/distributions.csv",
    "output/final_eda/lagged_relationships.csv",
    "output/final_eda/quality_counts.csv",
    "output/final_eda/sensitivity-results.csv",
    "output/final_eda/summary.json",
    "output/final_eda/time_blocks.csv",
]

SVG_FOUR = [
    "output/final_eda/figures/fig1_monthly_coverage.svg",
    "output/final_eda/figures/fig2_discharge_distributions.svg",
    "output/final_eda/figures/fig3_lagged_correlations.svg",
    "output/final_eda/figures/fig4_sensitivity_rules.svg",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest_paths() -> list[str]:
    paths: list[str] = []
    for raw in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if len(line) < 70:
            continue
        parts = line.split()
        if len(parts) >= 3 and len(parts[0]) == 64 and all(c in "0123456789abcdef" for c in parts[0]):
            rel = parts[2]
            if rel.endswith("CN.md") or rel.endswith("CN.docx"):
                continue
            paths.append(rel)
    paths.append("submission-manifest.txt")
    return sorted(set(paths))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rel_paths = parse_manifest_paths()

    # Security & cleanliness check on text files before packaging
    for rel in rel_paths:
        p = COURSE_DIR / rel
        assert p.is_file(), f"Missing manifest file: {p}"
        assert p.suffix.lower() not in {".key", ".pem", ".exe", ".dll", ".env"}, f"Disallowed suffix: {rel}"
        if p.suffix.lower() in {".py", ".md", ".txt", ".json"} and p.stat().st_size < 500_000:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            assert "Protected A" not in txt or "Protected A" in txt and "excluded" in txt.lower(), f"Check Protected A in {rel}"
            assert "BEGIN PRIVATE KEY" not in txt and "Bearer eyJ" not in txt, f"Secret pattern in {rel}"

    # Build ZIP (course-relative structure; sanitize out-of-ZIP cross-repo links inside staged .md copies only)
    member_set = set(rel_paths)
    t0 = time.perf_counter()
    sanitized_hashes: dict[str, tuple[str, int]] = {}
    staged_md: dict[str, bytes] = {}
    for rel in rel_paths:
        if rel.endswith(".md"):
            orig_txt = (COURSE_DIR / rel).read_text(encoding="utf-8")
            clean_txt = sanitize_zip_md(rel, orig_txt, member_set)
            b = clean_txt.encode("utf-8")
            staged_md[rel] = b
            sanitized_hashes[rel] = (hashlib.sha256(b).hexdigest(), len(b))

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel in rel_paths:
            if rel in staged_md:
                zf.writestr(rel, staged_md[rel])
            elif rel == "submission-manifest.txt":
                # Update ZIP-internal manifest hashes for any link-sanitized .md files while preserving repo manifest untouched
                out_lines = []
                for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
                    parts = line.split()
                    if len(parts) >= 3 and len(parts[0]) == 64 and parts[2] in sanitized_hashes:
                        h_new, b_new = sanitized_hashes[parts[2]]
                        tail = line.split(parts[2], 1)[1]
                        out_lines.append(f"{h_new}  {b_new:10d}  {parts[2]}{tail}")
                    else:
                        out_lines.append(line)
                zf.writestr(rel, ("\n".join(out_lines) + "\n").encode("utf-8"))
            else:
                zf.write(COURSE_DIR / rel, arcname=rel)
    build_s = round(time.perf_counter() - t0, 3)

    zip_bytes = ZIP_PATH.stat().st_size
    zip_sha = sha256_file(ZIP_PATH)

    # Clean extraction verification in an isolated temp directory
    tmp_root = Path(tempfile.mkdtemp(prefix="aida2156_zip_check_"))
    try:
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            zf.extractall(tmp_root)

        expected_hashes = {rel: sha256_file(tmp_root / rel) for rel in FROZEN_SEVEN + SVG_FOUR}

        # Delete pre-saved outputs inside extracted copy to prove fresh from-scratch standard-library replay
        for rel in FROZEN_SEVEN + SVG_FOUR:
            (tmp_root / rel).unlink()

        t_run = time.perf_counter()
        cmd1 = [sys.executable, "-B", "-E", "-S", "analysis/analysis.py"]
        r1 = subprocess.run(cmd1, cwd=tmp_root, capture_output=True, text=True, check=True)
        t_analysis = round(time.perf_counter() - t_run, 3)

        t_t = time.perf_counter()
        cmd2 = [sys.executable, "-B", "-E", "-S", "analysis/tests_or_assertions.py"]
        r2 = subprocess.run(cmd2, cwd=tmp_root, capture_output=True, text=True, check=True)
        t_tests = round(time.perf_counter() - t_t, 3)

        t_f = time.perf_counter()
        cmd3 = [sys.executable, "-B", "-E", "-S", "analysis/make_eda_figures.py"]
        r3 = subprocess.run(cmd3, cwd=tmp_root, capture_output=True, text=True, check=True)
        t_figs = round(time.perf_counter() - t_f, 3)

        # Verify byte-for-byte parity on all 7 tables + 4 SVGs and strict XML validity on SVGs
        mismatches = []
        for rel in FROZEN_SEVEN + SVG_FOUR:
            got = sha256_file(tmp_root / rel)
            if got != expected_hashes[rel]:
                mismatches.append(rel)
        for rel in SVG_FOUR:
            ET.fromstring((tmp_root / rel).read_bytes())

        assert not mismatches, f"Replay hash mismatches: {mismatches}"

        audit = {
            "validated_utc": datetime.now(timezone.utc).isoformat(),
            "zip_name": ZIP_PATH.name,
            "zip_bytes": zip_bytes,
            "zip_mb": round(zip_bytes / (1024 * 1024), 2),
            "zip_sha256": zip_sha,
            "file_count": len(rel_paths),
            "python_version": sys.version.split()[0],
            "stdlib_only_flags": "-B -E -S",
            "build_seconds": build_s,
            "clean_extract_replay": {
                "analysis_exit_code": r1.returncode,
                "analysis_seconds": t_analysis,
                "assertions_exit_code": r2.returncode,
                "assertions_seconds": t_tests,
                "figures_exit_code": r3.returncode,
                "figures_seconds": t_figs,
                "table_files_byte_matched": len(FROZEN_SEVEN),
                "svg_files_byte_matched_and_xml_valid": len(SVG_FOUR),
                "mismatches": 0,
            },
            "excluded": [
                "*CN.md and *CN.docx local companions",
                "raw acquisition archives, PostgreSQL/V4 model weights, Windows server/client binaries, .env credentials",
            ],
        }
        AUDIT_JSON.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, indent=2))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
