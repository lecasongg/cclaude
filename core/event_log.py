from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class EventLog:
    def __init__(self, root: str | Path, index_db_path: str | Path | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_db_path = Path(index_db_path) if index_db_path else None
        self._db: sqlite3.Connection | None = None
        if self.index_db_path:
            self.index_db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self.index_db_path)
            self._db.row_factory = sqlite3.Row
            self._initialize_index()

    def write_event(
        self,
        run_id: str,
        event_type: str,
        agent_id: str = "",
        step_id: str = "",
        payload: dict | None = None,
    ) -> dict:
        event = {
            "event_id": f"evt-{uuid4().hex}",
            "run_id": run_id,
            "type": event_type,
            "agent_id": agent_id,
            "step_id": step_id,
            "created_at": datetime.now(UTC).isoformat(),
            "payload": payload or {},
        }
        with self._event_path(run_id).open("a", encoding="utf-8") as event_file:
            event_file.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        self._write_index(event)
        return event

    def read_events(self, run_id: str, agent_id: str = "", step_id: str = "") -> list[dict]:
        path = self._event_path(run_id)
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if agent_id and event.get("agent_id") != agent_id:
                continue
            if step_id and event.get("step_id") != step_id:
                continue
            events.append(event)
        return events

    def query_indexed_events(self, run_id: str) -> list[dict]:
        if self._db is None:
            return []
        rows = self._db.execute(
            """
            select event_id, run_id, type, agent_id, step_id, created_at, payload_json
            from events
            where run_id = ?
            order by rowid
            """,
            (run_id,),
        ).fetchall()
        events = []
        for row in rows:
            event = dict(row)
            event["payload"] = json.loads(event.pop("payload_json"))
            events.append(event)
        return events

    def _event_path(self, run_id: str) -> Path:
        return self.root / f"{run_id}.jsonl"

    def _initialize_index(self) -> None:
        assert self._db is not None
        with self._db:
            self._db.execute(
                """
                create table if not exists events (
                  event_id text primary key,
                  run_id text not null,
                  type text not null,
                  agent_id text not null,
                  step_id text not null,
                  created_at text not null,
                  payload_json text not null
                )
                """
            )
            self._db.execute("create index if not exists idx_events_run_id on events(run_id)")

    def _write_index(self, event: dict) -> None:
        if self._db is None:
            return
        with self._db:
            self._db.execute(
                """
                insert into events(event_id, run_id, type, agent_id, step_id, created_at, payload_json)
                values(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    event["run_id"],
                    event["type"],
                    event["agent_id"],
                    event["step_id"],
                    event["created_at"],
                    json.dumps(event["payload"], ensure_ascii=False, sort_keys=True),
                ),
            )
