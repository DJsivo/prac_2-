$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = "reports/performance_fullchain"
$benchUser = "bench_" + $timestamp.Replace("_","")
$benchEmail = "$benchUser@example.com"

if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

py -3 tests/full_chain_transport_benchmark.py `
  --base-url http://localhost:8000 `
  --runs 100 `
  --warmup 5 `
  --username $benchUser `
  --email $benchEmail `
  --out-dir $outDir

if ($LASTEXITCODE -ne 0) {
    throw "full_chain_transport_benchmark.py failed with exit code $LASTEXITCODE"
}

Write-Output ""
Write-Output "Full-chain benchmark completed. Check files in: $outDir"
