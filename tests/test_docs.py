from pathlib import Path


def test_operator_quickstart_documents_current_commands():
    content = (Path(__file__).parents[1] / "docs" / "marvis-operator-quickstart.md").read_text(encoding="utf-8")

    assert "python serve.py" in content
    assert "python marvisctl.py status" in content
    assert "python marvisctl.py preflight" in content
    assert "python marvisctl.py compliance run" in content
    assert "python marvisctl.py compliance reports" in content
    assert "python scripts\\marvis_smoke.py" in content
    assert "python -m pytest tests/ -q" in content
