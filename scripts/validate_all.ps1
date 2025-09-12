$ErrorActionPreference = 'Stop'

# Discover corpus directory (env override or default to repo/corpus)
if ($env:CORPUS_DIR) {
  $CorpusDir = $env:CORPUS_DIR
} else {
  $RepoRoot = Join-Path $PSScriptRoot '..'
  $CorpusDir = Join-Path $RepoRoot 'corpus'
}

if (-not (Test-Path $CorpusDir)) {
  Write-Host "Corpus directory not found: $CorpusDir" -ForegroundColor Red
  exit 1
}

$CmdTemplate = if ($env:VALIDATOR_CMD) { $env:VALIDATOR_CMD } else { 'uv run dd-val --dict {dict} --data {data} --out {out} --html {html}' }

Write-Host "Discovering version directories under $CorpusDir …"
$versionDirs = Get-ChildItem -Path $CorpusDir -Recurse -Directory | Where-Object {
  Test-Path (Join-Path $_.FullName 'dictionary.csv') -and `
  Test-Path (Join-Path $_.FullName 'dataset.csv')
} | Sort-Object FullName

foreach ($dir in $versionDirs) {
  $dict = Join-Path $dir.FullName 'dictionary.csv'
  $data = Join-Path $dir.FullName 'dataset.csv'
  $out  = Join-Path $dir.FullName 'findings.json'
  $html = Join-Path $dir.FullName 'report.html'

  $cmd = $CmdTemplate.Replace('{dict}', $dict).Replace('{data}', $data).Replace('{out}', $out).Replace('{html}', $html)
  Write-Host "[validate] $($dir.FullName)" -ForegroundColor Cyan
  Invoke-Expression $cmd

  # Optional: fail on errors for clean runs (no gold.json present)
  if ($env:CLEAN_STRICT -and -not (Test-Path (Join-Path $dir.FullName 'gold.json'))) {
    if (Test-Path $out) {
      $raw = Get-Content -Raw -Path $out
      try {
        $obj = $raw | ConvertFrom-Json
      } catch {
        throw "Failed to parse findings: $out"
      }
      if ($obj -is [Array]) {
        $findings = $obj
      } else {
        $findings = $obj.findings
      }
      if ($findings) {
        $errors = @($findings | Where-Object { $_.severity -eq 'error' }).Count
        $warns  = @($findings | Where-Object { $_.severity -eq 'warn' }).Count
        Write-Host "[clean-noise] errors=$errors warnings=$warns file=$out"
        if ($errors -gt 0) { throw "Clean run produced errors: $out" }
      }
    }
  }
}

Write-Host "Done." -ForegroundColor Green

