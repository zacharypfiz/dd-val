#!/usr/bin/env bash
set -euo pipefail

# Validate all version directories that contain dictionary.csv + dataset.csv.
# Provide VALIDATOR_CMD as a template with placeholders:
#   {dict} {data} {out} {html}
# Defaults to: uv run dd-val --dict {dict} --data {data} --out {out} --html {html}

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
CORPUS_DIR="${CORPUS_DIR:-$ROOT_DIR/corpus}"
CLEAN_STRICT=${CLEAN_STRICT:-}

if [[ -z "${VALIDATOR_CMD:-}" ]]; then
  VALIDATOR_CMD='uv run dd-val --dict {dict} --data {data} --out {out} --html {html}'
fi

echo "Discovering project versions (by presence of dictionary.csv + dataset.csv)…"
find "$CORPUS_DIR" -type f -name 'dictionary.csv' -print0 |
while IFS= read -r -d '' dictfile; do
  proj_dir=$(dirname "$dictfile")
  dict="$proj_dir/dictionary.csv"
  data="$proj_dir/dataset.csv"
  [[ -f "$data" ]] || continue
  out="$proj_dir/findings.json"
  html="$proj_dir/report.html"
  cmd=${VALIDATOR_CMD//\{dict\}/$dict}
  cmd=${cmd//\{data\}/$data}
  cmd=${cmd//\{out\}/$out}
  cmd=${cmd//\{html\}/$html}
  echo "[validate] $proj_dir"
  eval "$cmd"
  # Optional clean noise gate: only apply when there's no gold.json in the same directory
  if [[ -n "$CLEAN_STRICT" && ! -f "$proj_dir/gold.json" ]]; then
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
done

echo "Done."
