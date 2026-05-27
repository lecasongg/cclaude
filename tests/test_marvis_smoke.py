import json
import subprocess
import sys


def test_marvis_smoke_script_runs_end_to_end():
    result = subprocess.run(
        [sys.executable, "scripts/marvis_smoke.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["status"] == "ok"
    assert body["run_id"].startswith("run-")
