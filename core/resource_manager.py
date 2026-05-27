from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from time import time
from uuid import uuid4


class ResourceManagerError(ValueError):
    pass


class ResourceConflictError(ResourceManagerError):
    pass


class ResourceManager:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._initialize_schema()

    def register_agent(
        self,
        agent_id: str,
        display_name: str,
        group: str = "",
        tags: list[str] | None = None,
    ) -> None:
        now = time()
        with self._db:
            self._db.execute(
                """
                insert into agents(agent_id, display_name, group_name, tags_json, created_at, updated_at)
                values(?, ?, ?, ?, ?, ?)
                on conflict(agent_id) do update set
                  display_name = excluded.display_name,
                  group_name = excluded.group_name,
                  tags_json = excluded.tags_json,
                  updated_at = excluded.updated_at
                """,
                (agent_id, display_name, group, json.dumps(tags or [], ensure_ascii=False), now, now),
            )
            self._db.execute(
                """
                insert into agent_state(agent_id, status, current_run_id, current_step_id, updated_at)
                values(?, 'idle', '', '', ?)
                on conflict(agent_id) do nothing
                """,
                (agent_id, now),
            )

    def get_agent(self, agent_id: str) -> dict:
        row = self._fetch_one("select * from agents where agent_id = ?", (agent_id,))
        return _agent_from_row(row)

    def get_agent_state(self, agent_id: str) -> dict:
        row = self._fetch_one("select * from agent_state where agent_id = ?", (agent_id,))
        return dict(row)

    def list_available_agents(self) -> list[dict]:
        rows = self._db.execute(
            """
            select agents.*
            from agents
            join agent_state on agent_state.agent_id = agents.agent_id
            where agent_state.status = 'idle'
            order by agents.agent_id
            """
        ).fetchall()
        return [_agent_from_row(row) for row in rows]

    def acquire_lease(self, agent_id: str, run_id: str, owner: str) -> str:
        self._ensure_agent(agent_id)
        existing = self._db.execute(
            "select lease_id from leases where agent_id = ? and released_at is null",
            (agent_id,),
        ).fetchone()
        if existing:
            raise ResourceConflictError(f"agent {agent_id} already leased")

        lease_id = f"lease-{uuid4().hex}"
        now = time()
        with self._db:
            self._db.execute(
                """
                insert into leases(lease_id, agent_id, run_id, owner, acquired_at, released_at)
                values(?, ?, ?, ?, ?, null)
                """,
                (lease_id, agent_id, run_id, owner, now),
            )
            self._db.execute(
                """
                update agent_state
                set status = 'reserved', current_run_id = ?, current_step_id = '', updated_at = ?
                where agent_id = ?
                """,
                (run_id, now, agent_id),
            )
        return lease_id

    def release_lease(self, lease_id: str) -> None:
        lease = self._fetch_one("select * from leases where lease_id = ?", (lease_id,))
        now = time()
        with self._db:
            self._db.execute(
                "update leases set released_at = ? where lease_id = ? and released_at is null",
                (now, lease_id),
            )
            self._db.execute(
                """
                update agent_state
                set status = 'idle', current_run_id = '', current_step_id = '', updated_at = ?
                where agent_id = ?
                """,
                (now, lease["agent_id"]),
            )

    def create_pipeline_run(self, title: str) -> str:
        run_id = f"run-{uuid4().hex}"
        now = time()
        with self._db:
            self._db.execute(
                """
                insert into pipeline_runs(run_id, title, status, created_at, updated_at)
                values(?, ?, 'queued', ?, ?)
                """,
                (run_id, title, now, now),
            )
        return run_id

    def get_pipeline_run(self, run_id: str) -> dict:
        return dict(self._fetch_one("select * from pipeline_runs where run_id = ?", (run_id,)))

    def list_pipeline_runs(self) -> list[dict]:
        rows = self._db.execute(
            "select * from pipeline_runs order by created_at desc"
        ).fetchall()
        return [dict(row) for row in rows]

    def update_pipeline_status(self, run_id: str, status: str) -> None:
        self._ensure_pipeline_run(run_id)
        with self._db:
            self._db.execute(
                "update pipeline_runs set status = ?, updated_at = ? where run_id = ?",
                (status, time(), run_id),
            )

    def create_step_run(
        self,
        run_id: str,
        step_id: str,
        agent_id: str,
        objective: str,
        depends_on: list[str] | None = None,
        outputs: list[str] | None = None,
        self_check: list[str] | None = None,
    ) -> None:
        self._ensure_pipeline_run(run_id)
        self._ensure_agent(agent_id)
        now = time()
        with self._db:
            self._db.execute(
                """
                insert into step_runs(run_id, step_id, agent_id, objective, status, depends_on_json, outputs_json, self_check_json, created_at, updated_at)
                values(?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    step_id,
                    agent_id,
                    objective,
                    json.dumps(depends_on or [], ensure_ascii=False),
                    json.dumps(outputs or [], ensure_ascii=False),
                    json.dumps(self_check or [], ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def get_step_run(self, run_id: str, step_id: str) -> dict:
        row = self._fetch_one(
            "select * from step_runs where run_id = ? and step_id = ?",
            (run_id, step_id),
        )
        step = dict(row)
        step["depends_on"] = json.loads(step.pop("depends_on_json"))
        step["outputs"] = json.loads(step.pop("outputs_json"))
        step["self_check"] = json.loads(step.pop("self_check_json"))
        return step

    def list_step_runs(self, run_id: str) -> list[dict]:
        self._ensure_pipeline_run(run_id)
        rows = self._db.execute(
            "select * from step_runs where run_id = ? order by created_at",
            (run_id,),
        ).fetchall()
        steps = []
        for row in rows:
            step = dict(row)
            step["depends_on"] = json.loads(step.pop("depends_on_json"))
            step["outputs"] = json.loads(step.pop("outputs_json"))
            step["self_check"] = json.loads(step.pop("self_check_json"))
            steps.append(step)
        return steps

    def update_step_status(self, run_id: str, step_id: str, status: str) -> None:
        self.get_step_run(run_id, step_id)
        with self._db:
            self._db.execute(
                """
                update step_runs
                set status = ?, updated_at = ?
                where run_id = ? and step_id = ?
                """,
                (status, time(), run_id, step_id),
            )

    def reconcile_on_startup(self) -> dict:
        """Move uncertain in-flight state to blocked after a server restart.

        The current P0 runtime executes steps synchronously. If the API server
        restarts while a run is marked running/reserved, we cannot prove the
        external worker process is still healthy, so the safest recovery state
        is blocked with leases released. Users can inspect artifacts/events and
        rerun once the correction/rerun flow exists.
        """
        now = time()
        with self._db:
            active_leases = self._db.execute(
                "select lease_id from leases where released_at is null"
            ).fetchall()
            blocked_steps = self._db.execute(
                """
                update step_runs
                set status = 'blocked', updated_at = ?
                where status in ('queued', 'reserved', 'running', 'waiting')
                """,
                (now,),
            ).rowcount
            blocked_runs = self._db.execute(
                """
                update pipeline_runs
                set status = 'blocked', updated_at = ?
                where status in ('queued', 'reserved', 'running', 'waiting')
                """,
                (now,),
            ).rowcount
            self._db.execute(
                "update leases set released_at = ? where released_at is null",
                (now,),
            )
            reset_agents = self._db.execute(
                """
                update agent_state
                set status = 'idle', current_run_id = '', current_step_id = '', updated_at = ?
                where status in ('reserved', 'running', 'waiting', 'blocked')
                """,
                (now,),
            ).rowcount
        return {
            "released_leases": len(active_leases),
            "blocked_runs": blocked_runs,
            "blocked_steps": blocked_steps,
            "reset_agents": reset_agents,
        }

    def _initialize_schema(self) -> None:
        with self._db:
            self._db.executescript(
                """
                create table if not exists agents (
                  agent_id text primary key,
                  display_name text not null,
                  group_name text not null default '',
                  tags_json text not null default '[]',
                  created_at real not null,
                  updated_at real not null
                );

                create table if not exists agent_state (
                  agent_id text primary key,
                  status text not null,
                  current_run_id text not null default '',
                  current_step_id text not null default '',
                  updated_at real not null,
                  foreign key(agent_id) references agents(agent_id)
                );

                create table if not exists leases (
                  lease_id text primary key,
                  agent_id text not null,
                  run_id text not null,
                  owner text not null,
                  acquired_at real not null,
                  released_at real,
                  foreign key(agent_id) references agents(agent_id)
                );

                create table if not exists pipeline_runs (
                  run_id text primary key,
                  title text not null,
                  status text not null,
                  created_at real not null,
                  updated_at real not null
                );

                create table if not exists step_runs (
                  run_id text not null,
                  step_id text not null,
                  agent_id text not null,
                  objective text not null,
                  status text not null,
                  depends_on_json text not null default '[]',
                  outputs_json text not null default '[]',
                  self_check_json text not null default '[]',
                  created_at real not null,
                  updated_at real not null,
                  primary key(run_id, step_id),
                  foreign key(run_id) references pipeline_runs(run_id),
                  foreign key(agent_id) references agents(agent_id)
                );
                """
            )
            self._ensure_column("step_runs", "outputs_json", "text not null default '[]'")
            self._ensure_column("step_runs", "self_check_json", "text not null default '[]'")

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self._db.execute(f"pragma table_info({table})").fetchall()}
        if column not in columns:
            self._db.execute(f"alter table {table} add column {column} {definition}")

    def _ensure_agent(self, agent_id: str) -> None:
        self._fetch_one("select agent_id from agents where agent_id = ?", (agent_id,))

    def _ensure_pipeline_run(self, run_id: str) -> None:
        self._fetch_one("select run_id from pipeline_runs where run_id = ?", (run_id,))

    def _fetch_one(self, query: str, params: tuple = ()) -> sqlite3.Row:
        row = self._db.execute(query, params).fetchone()
        if row is None:
            raise ResourceManagerError("record not found")
        return row


def _agent_from_row(row: sqlite3.Row) -> dict:
    agent = dict(row)
    agent["tags"] = json.loads(agent.pop("tags_json"))
    return agent
