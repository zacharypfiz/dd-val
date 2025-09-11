#!/usr/bin/env bash
set -euo pipefail

# Runs a validator CLI over all perturbed projects.
# Provide VALIDATOR_CMD as a template with placeholders:
#   {dict} {data} {out} {html}
# Example:
#   VALIDATOR_CMD='dd-val --dict {dict} --data {data} --out {out} --html {html}' scripts/validate_all.sh

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
CORPUS_DIR="${CORPUS_DIR:-$ROOT_DIR/corpus}"
CLEAN_STRICT=${CLEAN_STRICT:-}

if [[ -z "${VALIDATOR_CMD:-}" ]]; then
  echo "VALIDATOR_CMD is not set. Skipping validation runs."
  echo "Set VALIDATOR_CMD='your_cli --dict {dict} --data {data} --out {out} --html {html}' and rerun."
  exit 0
fi

echo "Running on CLEAN projects…"
shopt -s nullglob
for proj in "$CORPUS_DIR"/*_clean; do
  if [[ -d "$proj" ]]; then
    dict="$proj/dictionary.csv"
    data="$proj/dataset.csv"
    out="$proj/findings.json"
    html="$proj/report.html"
    cmd=${VALIDATOR_CMD//\{dict\}/$dict}
    cmd=${cmd//\{data\}/$data}
    cmd=${cmd//\{out\}/$out}
    cmd=${cmd//\{html\}/$html}
    echo "[validate:clean] $proj"
    eval "$cmd"
    if [[ -n "$CLEAN_STRICT" ]]; then
      # Fail if any errors are present in clean findings
      python3 - "$out" <<'PY'
import json, sys, pathlib
p=pathlib.Path(sys.argv[1])
obj=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
findings=obj.get('findings', []) if isinstance(obj, dict) else obj
errs=[f for f in findings if isinstance(f, dict) and f.get('severity')=='error']
warns=[f for f in findings if isinstance(f, dict) and f.get('severity')=='warn']
print(f"[clean-noise] errors={len(errs)} warnings={len(warns)} file={p}")
sys.exit(1 if errs else 0)
PY
    fi
  fi
done

echo "Running on PERTURBED projects…"
shopt -s nullglob
for proj in "$CORPUS_DIR"/*_perturbed*; do
  if [[ -d "$proj" ]]; then
    dict="$proj/dictionary.csv"
    data="$proj/dataset.csv"
    out="$proj/findings.json"
    html="$proj/report.html"
    # Try to set prev for _v2 runs using sibling _perturbed findings
    prev=""
    if [[ "$proj" == *_perturbed_v2 ]]; then
      base="${proj%_perturbed_v2}"
      prev_file="$base""_perturbed/findings.json"
      if [[ -f "$prev_file" ]]; then
        prev="--prev $prev_file"
      fi
    fi
    cmd=${VALIDATOR_CMD//\{dict\}/$dict}
    cmd=${cmd//\{data\}/$data}
    cmd=${cmd//\{out\}/$out}
    cmd=${cmd//\{html\}/$html}
    if [[ -n "$prev" ]]; then
      cmd="$cmd $prev"
    fi
    echo "[validate] $proj"
    eval "$cmd"
  fi
done

echo "Done."
