import json

from agent_factory.core.event_log import EventLog


def test_event_log_appends_run_events_without_overwriting(tmp_path):
    log = EventLog(tmp_path / "events")

    first = log.write_event("run-1", "run_created", payload={"title": "登录模块改造"})
    second = log.write_event("run-1", "step_started", agent_id="niuma-1", step_id="reverse-login")

    events_path = tmp_path / "events" / "run-1.jsonl"
    lines = events_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0])["event_id"] == first["event_id"]
    assert json.loads(lines[1])["event_id"] == second["event_id"]
    assert [event["type"] for event in log.read_events("run-1")] == ["run_created", "step_started"]


def test_event_log_filters_by_agent_and_step(tmp_path):
    log = EventLog(tmp_path / "events")
    log.write_event("run-1", "step_started", agent_id="niuma-1", step_id="reverse-login")
    log.write_event("run-1", "step_started", agent_id="niuma-2", step_id="write-requirements")
    log.write_event("run-1", "agent_progress", agent_id="niuma-1", step_id="reverse-login")

    filtered = log.read_events("run-1", agent_id="niuma-1", step_id="reverse-login")

    assert [event["type"] for event in filtered] == ["step_started", "agent_progress"]
    assert {event["agent_id"] for event in filtered} == {"niuma-1"}


def test_event_log_persists_sqlite_index_for_queries(tmp_path):
    db_path = tmp_path / "events.db"
    log = EventLog(tmp_path / "events", index_db_path=db_path)

    written = log.write_event(
        "run-1",
        "artifact_written",
        agent_id="niuma-1",
        step_id="reverse-login",
        payload={"path": "artifacts/runs/run-1/reverse-login/function-list.md"},
    )

    reopened = EventLog(tmp_path / "events", index_db_path=db_path)
    indexed = reopened.query_indexed_events("run-1")

    assert indexed[0]["event_id"] == written["event_id"]
    assert indexed[0]["type"] == "artifact_written"
    assert indexed[0]["payload"] == {"path": "artifacts/runs/run-1/reverse-login/function-list.md"}
