import os
import sys
from pathlib import Path


def main() -> int:
    worker_id = os.environ["NIUMA_WORKER_ID"]
    provider = os.environ["NIUMA_PROVIDER"]
    model = os.environ["NIUMA_MODEL"]
    workspace_dir = Path(os.environ["NIUMA_WORKSPACE_DIR"])
    skills_dir = Path(os.environ["NIUMA_SKILLS_DIR"])
    prompt_path = Path(sys.argv[1])
    result_path = Path(sys.argv[2])

    prompt = prompt_path.read_text(encoding="utf-8")
    workspace_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    result_path.write_text(
        "\n".join(
            [
                f"# {worker_id} 试运行结果",
                "",
                f"- provider: {provider}",
                f"- model: {model}",
                f"- workspace: {workspace_dir}",
                f"- skills: {skills_dir}",
                "",
                "## 收到的任务",
                prompt,
                "",
                "## 输出",
                f"{worker_id} 已在独立子进程中完成任务。",
            ]
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
