from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List


def read_csv(path: os.PathLike[str] | str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def write_csv(path: os.PathLike[str] | str, rows: Iterable[Dict[str, str]], headers: List[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (r.get(k, "") if r.get(k, "") is not None else "") for k in headers})


def write_json(path: os.PathLike[str] | str, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def read_json(path: os.PathLike[str] | str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def slug(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in s)


def rnd_choice(rng, seq):
    return seq[rng.randrange(0, len(seq))]


def ensure_dir(path: os.PathLike[str] | str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)
