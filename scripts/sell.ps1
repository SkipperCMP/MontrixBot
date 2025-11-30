
Param(
  [Parameter(Mandatory=$true)][string]$Symbol,
  [Parameter(Mandatory=$true)][string]$Qty,
  [Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Set-Location $root
$py = (Get-Command python).Source
$script = Join-Path $here "real_sell_market.py"
$argv = @($script, $Symbol, $Qty) + $Rest
& $py $argv
