
Param(
  [Parameter(Mandatory=$true)][string]$Symbol,
  [Parameter(Mandatory=$true)][string]$Qty,
  [Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest
)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$ask = $true
if ($Rest -contains "--no-ask") { $ask = $false }
$py = (Get-Command python).Source
$script = Join-Path $PSScriptRoot "real_buy_market.py"
if (-not (Test-Path $script)) {
  Write-Error "Script not found: $script"
  exit 1
}
$argv = @($script, $Symbol, $Qty)
if ($ask) { $argv += "--ask" }
& $py $argv
