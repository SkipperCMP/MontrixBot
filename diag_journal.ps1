$paths = @(
  "runtime\events.jsonl",
  "runtime\logs\events.jsonl",
  "runtime\logs\events.jsonl".Replace("\logs\events.jsonl","\events.jsonl")
)

$uniq = $paths | Select-Object -Unique
Write-Host "=== MontrixBot Journal Diagnostics ==="

foreach ($p in $uniq) {
  $exists = [System.IO.File]::Exists($p)
  if ($exists) {
    $len = (Get-Item $p).Length
    Write-Host ("OK  : {0}  ({1} bytes)" -f $p, $len)
  } else {
    Write-Host ("MISS: {0}" -f $p)
  }
}

Write-Host ""
Write-Host "=== Search SIM_DECISION_JOURNAL ==="
foreach ($p in $uniq) {
  if ([System.IO.File]::Exists($p)) {
    $hit = Select-String -Path $p -Pattern "SIM_DECISION_JOURNAL" -List -ErrorAction SilentlyContinue
    if ($hit) { Write-Host ("FOUND in {0}" -f $p) } else { Write-Host ("NOHIT in {0}" -f $p) }
  }
}

Write-Host ""
Write-Host "=== First 3 lines (if exists) ==="
foreach ($p in $uniq) {
  if ([System.IO.File]::Exists($p)) {
    Write-Host ("--- {0} ---" -f $p)
    Get-Content $p -TotalCount 3 | ForEach-Object { $_ }
  }
}
