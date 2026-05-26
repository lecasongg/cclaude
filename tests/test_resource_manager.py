import pytest

from agent_factory.core.resource_manager import ResourceConflictError, ResourceManager


def test_resource_manager_persists_registered_agents(tmp_path):
    db_path = tmp_path / "marvis.db"
    manager = ResourceManager(db_path)

    manager.register_agent(
        "niuma-1",
        display_name="牛马1",
        group="legacy-modernization",
        tags=["jsp", "reverse-engineering"],
    )

    reopened = ResourceManager(db_path)

    agent = reopened.get_agent("niuma-1")
    assert agent["agent_id"] == "niuma-1"
    assert agent["display_name"] == "牛马1"
    assert agent["group_name"] == "legacy-modernization"
    assert agent["tags"] == ["jsp", "reverse-engineering"]
    assert reopened.get_agent_state("niuma-1")["status"] == "idle"


def test_resource_manager_prevents_double_lease_for_same_agent(tmp_path):
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="牛马1")

    lease_id = manager.acquire_lease("niuma-1", run_id="run-1", owner="scheduler-a")

    with pytest.raises(ResourceConflictError, match="agent niuma-1 already leased"):
        manager.acquire_lease("niuma-1", run_id="run-2", owner="scheduler-b")

    manager.release_lease(lease_id)
    second_lease_id = manager.acquire_lease("niuma-1", run_id="run-2", owner="scheduler-b")

    assert second_lease_id != lease_id
    assert manager.get_agent_state("niuma-1")["status"] == "reserved"


def test_resource_manager_persists_pipeline_and_step_state(tmp_path):
    db_path = tmp_path / "marvis.db"
    manager = ResourceManager(db_path)
    manager.register_agent("niuma-1", display_name="牛马1")

    run_id = manager.create_pipeline_run("老系统登录模块改造")
    manager.create_step_run(
        run_id,
        step_id="reverse-login",
        agent_id="niuma-1",
        objective="逆向登录模块",
        depends_on=[],
    )
    manager.update_step_status(run_id, "reverse-login", "running")
    manager.update_pipeline_status(run_id, "running")

    reopened = ResourceManager(db_path)

    run = reopened.get_pipeline_run(run_id)
    step = reopened.get_step_run(run_id, "reverse-login")
    assert run["title"] == "老系统登录模块改造"
    assert run["status"] == "running"
    assert step["agent_id"] == "niuma-1"
    assert step["objective"] == "逆向登录模块"
    assert step["status"] == "running"
    assert step["depends_on"] == []


def test_resource_manager_lists_available_agents(tmp_path):
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="牛马1", tags=["jsp"])
    manager.register_agent("niuma-2", display_name="牛马2", tags=["requirements"])
    manager.acquire_lease("niuma-1", run_id="run-1", owner="scheduler-a")

    available = manager.list_available_agents()

    assert [agent["agent_id"] for agent in available] == ["niuma-2"]
