from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def _load_gold_and_findings(run_dir: Path) -> Tuple[List[dict], List[dict]]:
    gold_path = run_dir / "gold.json"
    findings_path = run_dir / "findings.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8")) if gold_path.exists() else []
    findings_raw = json.loads(findings_path.read_text(encoding="utf-8")) if findings_path.exists() else []
    if isinstance(findings_raw, dict):
        findings = findings_raw.get("findings", [])
    else:
        findings = findings_raw
    return gold, findings


def _key(issue: dict, mode: str = "variable") -> Tuple[str, str]:
    t = issue.get("type", "")
    if mode == "strict":
        v = issue.get("variable", "")
        e = json.dumps(issue.get("expected"), sort_keys=True) if "expected" in issue else ""
        o = json.dumps(issue.get("observed"), sort_keys=True) if "observed" in issue else ""
        return (t, f"{v}|{e}|{o}")
    else:
        return (t, issue.get("variable", ""))


def score_corpus(corpus_dir: str | Path, mode: str = "variable") -> Dict[str, Dict[str, float]]:
    base = Path(corpus_dir)
    # Discover all run dirs that contain a gold.json (layout-agnostic)
    runs = sorted(p.parent for p in base.rglob("gold.json"))
    tp: Dict[str, int] = defaultdict(int)
    fp: Dict[str, int] = defaultdict(int)
    fn: Dict[str, int] = defaultdict(int)

    for run in runs:
        gold, findings = _load_gold_and_findings(run)
        gold_keys = {(t, k) for (t, k) in (_key(g, mode) for g in gold)}
        pred_keys = {(t, k) for (t, k) in (_key(f, mode) for f in findings)}

        types = {t for (t, _k) in gold_keys | pred_keys}
        for t in types:
            gset = {k for (tt, k) in gold_keys if tt == t}
            pset = {k for (tt, k) in pred_keys if tt == t}
            tp[t] += len(gset & pset)
            fp[t] += len(pset - gset)
            fn[t] += len(gset - pset)

    metrics: Dict[str, Dict[str, float]] = {}
    for t in sorted({*tp.keys(), *fp.keys(), *fn.keys()}):
        p = tp[t] / (tp[t] + fp[t]) if (tp[t] + fp[t]) else 0.0
        r = tp[t] / (tp[t] + fn[t]) if (tp[t] + fn[t]) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        metrics[t] = {"precision": p, "recall": r, "f1": f1}
    return metrics


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Score findings.json against gold.json across corpus")
    ap.add_argument("--corpus", default="corpus", help="Corpus directory (default: corpus)")
    ap.add_argument("--mode", choices=["variable", "strict"], default="variable", help="Match mode (default: variable)")
    args = ap.parse_args(argv)

    metrics = score_corpus(args.corpus, args.mode)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
