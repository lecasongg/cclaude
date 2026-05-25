param()

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
$env:PYTHONPATH = (Resolve-Path (Join-Path $Root ".."))
python (Join-Path $Root "worker_server.py")
