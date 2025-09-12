from __future__ import annotations

"""Seed a deterministic REDCap evaluation corpus (clean + perturbed v1/v2).

Writes a nested, versioned layout under `corpus/<project>/...`.
"""

import argparse
import os
from pathlib import Path
from typing import List

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
        proj_root = out / proj
        print(f"[seed] Building {proj}…")
        d_rows, x_rows = dictionary_and_data(i, rows_per_project, seed)

        # Clean v1
        clean_v1 = proj_root / "clean" / "v1"
        ensure_dir(clean_v1)
        write_csv(clean_v1 / "dictionary.csv", d_rows, HEADERS)
        data_headers = list(x_rows[0].keys()) if x_rows else []
        write_csv(clean_v1 / "dataset.csv", x_rows, data_headers)

        # Perturbed v1
        p_rows, p_data, gold1 = apply_corruptions(d_rows, x_rows, seed + i)
        pert_v1 = proj_root / "perturbed" / "v1"
        ensure_dir(pert_v1)
        p_headers = list(p_data[0].keys()) if p_data else []
        write_csv(pert_v1 / "dictionary.csv", p_rows, HEADERS)
        write_csv(pert_v1 / "dataset.csv", p_data, p_headers)
        write_json(pert_v1 / "gold.json", gold1)

        # Perturbed v2 (since-last-run)
        p2_rows, p2_data, gold2_extra = apply_since_last_run(p_rows, p_data, seed + i)
        pert_v2 = proj_root / "perturbed" / "v2"
        ensure_dir(pert_v2)
        p2_headers = list(p2_data[0].keys()) if p2_data else []
        write_csv(pert_v2 / "dictionary.csv", p2_rows, HEADERS)
        write_csv(pert_v2 / "dataset.csv", p2_data, p2_headers)
        write_json(pert_v2 / "gold.json", gold1 + gold2_extra)


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
