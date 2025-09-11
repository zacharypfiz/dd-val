from __future__ import annotations

"""Seed a deterministic REDCap evaluation corpus (clean + perturbed + v2).

This script is CLI-wrapped via `dd-seed` and writes CSVs and gold.json records.
"""

import argparse
import os
from pathlib import Path
from typing import Dict, List

from .corrupt import apply_corruptions, apply_since_last_run
from .schema import HEADERS
from .synth import dictionary_and_data
from .util import ensure_dir, write_csv, write_json


def seed_corpus(
    out_dir: os.PathLike[str] | str,
    n_projects: int = 10,
    rows_per_project: int = 500,
    seed: int = 42,
) -> None:
    out = Path(out_dir)
    ensure_dir(out)

    for i in range(1, n_projects + 1):
        proj = f"proj{i:02d}"
        print(f"[seed] Building {proj}…")
        d_rows, x_rows = dictionary_and_data(i, rows_per_project, seed)

        # Clean
        clean_dir = out / f"{proj}_clean"
        write_csv(clean_dir / "dictionary.csv", d_rows, HEADERS)
        # Data headers for clean are driven by dictionary (checkbox expands)
        data_headers = list(x_rows[0].keys()) if x_rows else []
        write_csv(clean_dir / "dataset.csv", x_rows, data_headers)

        # Perturbed v1
        p_rows, p_data, gold1 = apply_corruptions(d_rows, x_rows, seed + i)
        perturbed_dir = out / f"{proj}_perturbed"
        write_csv(perturbed_dir / "dictionary.csv", p_rows, HEADERS)
        p_headers = list(p_data[0].keys()) if p_data else []
        write_csv(perturbed_dir / "dataset.csv", p_data, p_headers)
        write_json(perturbed_dir / "gold.json", gold1)

        # Perturbed v2 (since-last-run)
        p2_rows, p2_data, gold2_extra = apply_since_last_run(p_rows, p_data, seed + i)
        perturbed_v2_dir = out / f"{proj}_perturbed_v2"
        write_csv(perturbed_v2_dir / "dictionary.csv", p2_rows, HEADERS)
        p2_headers = list(p2_data[0].keys()) if p2_data else []
        write_csv(perturbed_v2_dir / "dataset.csv", p2_data, p2_headers)
        write_json(perturbed_v2_dir / "gold.json", gold1 + gold2_extra)


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Seed deterministic REDCap eval corpus")
    p.add_argument("--out", default="corpus", help="Output directory (default: corpus)")
    p.add_argument("--projects", type=int, default=10, help="Number of projects (default: 10)")
    p.add_argument("--rows", type=int, default=500, help="Rows per project (default: 500)")
    p.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    return p


def main(argv: List[str] | None = None) -> None:
    args = build_argparser().parse_args(argv)
    seed_corpus(args.out, args.projects, args.rows, args.seed)


if __name__ == "__main__":
    main()
