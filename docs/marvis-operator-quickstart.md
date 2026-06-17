# Marvis Operator Quickstart

This guide is the current operator path for the Marvis AI Factory prototype.

## Start The Factory

```powershell
cd D:\codex\cclaude
python serve.py
```

Open:

```text
http://127.0.0.1:8846/
```

Default API token:

```text
local-token
```

## Check Factory Status

```powershell
python marvisctl.py status --config factory_config.example.json --workspace .
```

JSON output:

```powershell
python marvisctl.py status --config factory_config.example.json --workspace . --json
```

## Preflight Before A Run

```powershell
python marvisctl.py preflight `
  --config factory_config.example.json `
  --taskbook taskbooks\legacy-module-modernization.yml `
  --source C:\Users\12799\Downloads\index.jsp `
  --suite tests\compliance
```

The launch gate checks:

- TaskBook syntax and dependency order
- TaskBook step agents are registered
- Source path exists and is readable
- Worker health
- Compliance suite shape

## Run Compliance

Quick mode does not call a real model:

```powershell
python marvisctl.py compliance run --suite tests\compliance --mode quick --workspace .tmp\compliance
```

Model mode uses configured workers:

```powershell
python marvisctl.py compliance run `
  --suite tests\compliance `
  --mode model `
  --config factory_config.example.json `
  --workspace .tmp\compliance-model
```

Reports are written under the selected workspace unless `--report-dir` is supplied.

## Browse Compliance Reports

```powershell
python marvisctl.py compliance reports --workspace .
```

```powershell
python marvisctl.py compliance show compliance-quick-20260101T000000Z-passed.json --workspace .
```

## Smoke Test The Factory Contract

```powershell
python scripts\marvis_smoke.py
```

This verifies the API, TaskBook execution, step dependencies, artifacts, quality gate, manifest, and correction rerun contract without spending model tokens.

## Regression Tests

```powershell
$env:TMP='D:\codex\cclaude\.tmp'
$env:TEMP='D:\codex\cclaude\.tmp'
$env:TMPDIR='D:\codex\cclaude\.tmp'
python -m pytest tests/ -q
```

