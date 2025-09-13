from __future__ import annotations

"""Self-test: seed a tiny corpus, run dd-val, and score results.

Usage:
  uv run scripts/selftest.py [--projects N] [--rows N] [--seed N] [--keep]

This script performs a fast, deterministic end-to-end check:
  1) Seeds a small evaluation corpus (clean + perturbed v1/v2)
  2) Runs the validator on every version directory
  3) Scores findings against the gold standard for perturbed runs
  4) Verifies clean runs have zero errors

It exits non-zero if assertions fail, making it CI-friendly.
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

# Local imports (no external deps)
from src.dd_eval.seed import seed_corpus
from src.dd_eval.score import score_corpus
from src.dd_val.cli import main as ddval_main


def _run_validator_over(base: Path) -> None:
    """Run dd-val over every directory that has dictionary.csv + dataset.csv.

    Ensures deterministic order so that v1 runs before v2 to enable since-last-run linking.
    """
    dict_files = sorted(base.rglob("dictionary.csv"))
    for dpath in dict_files:
        run_dir = dpath.parent
        data = run_dir / "dataset.csv"
        if not data.exists():
            continue
        out = run_dir / "findings.json"
        html = run_dir / "report.html"
        args = [
            "--dict",
            str(dpath),
            "--data",
            str(data),
            "--out",
            str(out),
            "--html",
            str(html),
        ]
        ddval_main(args)


def _collect_clean_runs_with_errors(base: Path) -> List[Tuple[Path, int]]:
    """Return list of (run_dir, error_count) for directories without gold.json that have errors."""
    offenders: List[Tuple[Path, int]] = []
    for dpath in sorted(base.rglob("dictionary.csv")):
        run_dir = dpath.parent
        gold = run_dir / "gold.json"
        if gold.exists():
            continue  # not a clean run (perturbed run has gold)
        findings_file = run_dir / "findings.json"
        if not findings_file.exists():
            continue
        try:
            raw = json.loads(findings_file.read_text(encoding="utf-8"))
            findings = raw.get("findings", []) if isinstance(raw, dict) else (raw or [])
        except Exception:
            continue
        errors = [f for f in findings if isinstance(f, dict) and f.get("severity") == "error"]
        if errors:
            offenders.append((run_dir, len(errors)))
    return offenders


def _gold_types(base: Path) -> List[str]:
    types: set[str] = set()
    for g in base.rglob("gold.json"):
        try:
            gold = json.loads(g.read_text(encoding="utf-8"))
            for rec in gold:
                t = (rec or {}).get("type")
                if t:
                    types.add(t)
        except Exception:
            pass
    return sorted(types)


def run_selftest(projects: int, rows: int, seed: int, keep: bool) -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="ddval-selftest-"))
    try:
        # 1) Seed a tiny corpus
        seed_corpus(tmp_dir, n_projects=projects, rows_per_project=rows, seed=seed)

        # 2) Run the validator across the corpus
        _run_validator_over(tmp_dir)

        # 3) Check clean runs for zero errors
        offenders = _collect_clean_runs_with_errors(tmp_dir)
        if offenders:
            print("Clean runs produced errors:", file=sys.stderr)
            for d, n in offenders:
                print(f"  - {d} errors={n}", file=sys.stderr)
            return 2

        # 4) Score perturbed runs against gold
        metrics: Dict[str, Dict[str, float]] = score_corpus(tmp_dir, mode="variable")
        present = _gold_types(tmp_dir)

        # Enforce a simple bar for all types present in gold
        FAIL_THRESHOLD = 0.90  # per-type F1 minimum
        failing: List[Tuple[str, float]] = []
        for t in present:
            m = metrics.get(t) or {}
            f1 = float(m.get("f1") or 0.0)
            if f1 < FAIL_THRESHOLD:
                failing.append((t, f1))

        # Summary
        print("Self-test summary:")
        print(f"  Corpus: {tmp_dir}")
        print(f"  Clean runs with errors: {len(offenders)}")
        print("  Per-type F1 (present in gold):")
        for t in present:
            m = metrics.get(t) or {}
            print(f"    - {t}: P={m.get('precision', 0):.2f} R={m.get('recall', 0):.2f} F1={m.get('f1', 0):.2f}")

        if failing:
            print("Failing thresholds:", file=sys.stderr)
            for t, f1 in failing:
                print(f"  - {t}: F1={f1:.2f} (< {FAIL_THRESHOLD:.2f})", file=sys.stderr)
            return 3

        print("OK ✅")
        return 0
    finally:
        if not keep:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="DD-Val self-test: seed, validate, and score")
    ap.add_argument("--projects", type=int, default=3, help="Projects to seed (default: 3)")
    ap.add_argument("--rows", type=int, default=200, help="Rows per project (default: 200)")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    ap.add_argument("--keep", action="store_true", help="Keep the temporary corpus directory (for debugging)")
    args = ap.parse_args(argv)

    code = run_selftest(args.projects, args.rows, args.seed, args.keep)
    sys.exit(code)


if __name__ == "__main__":
    main()

