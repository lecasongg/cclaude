param(
  [string]$BaseUrl = "http://127.0.0.1:8846",
  [string]$Token = "change-me-local-token",
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$HermesArgs
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
python (Join-Path $Root "hermes_supervisor.py") $BaseUrl $Token @HermesArgs
