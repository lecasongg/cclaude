from agent_factory.core.skill_linking import link_worker_skills


def test_link_worker_skills_creates_claude_skills_dir(tmp_path):
    skills_src = tmp_path / "skills/niuma-1/demo-skill"
    skills_src.mkdir(parents=True)
    (skills_src / "SKILL.md").write_text("---\nname: demo-skill\n---", encoding="utf-8")
    workspace = tmp_path / "workspaces/niuma-1"
    workspace.mkdir(parents=True)

    link_worker_skills(skills_dir=tmp_path / "skills/niuma-1", workspace_dir=workspace)

    linked = workspace / ".claude/skills/demo-skill/SKILL.md"
    assert linked.exists()
    assert "demo-skill" in linked.read_text(encoding="utf-8")
