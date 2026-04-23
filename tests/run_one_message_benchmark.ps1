$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = "reports/benchmarks"
$outFile = Join-Path $outDir ("one_message_" + $timestamp + ".txt")

if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

docker run --rm --network lab2_logistics_lab2_network `
  -v "${PWD}:/work" `
  -w /work `
  lab2_logistics-orders `
  python tests/interservice_one_message_benchmark.py --base-url http://notification:8004 --runs 30 --warmup 5 `
  | Tee-Object -FilePath $outFile

Write-Output ""
Write-Output "Saved benchmark result to: $outFile"
