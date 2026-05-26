import os
import shutil
import subprocess
import sys
from pathlib import Path


def link_worker_skills(skills_dir: Path, workspace_dir: Path) -> None:
    skills_dir = Path(skills_dir)
    workspace_dir = Path(workspace_dir)
    target_root = workspace_dir / ".claude" / "skills"
    target_root.mkdir(parents=True, exist_ok=True)

    if not skills_dir.exists():
        return

    for skill_path in skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
        target = target_root / skill_path.name
        if target.exists() or target.is_symlink():
            continue
        _link_or_copy(skill_path, target)


def _link_or_copy(source: Path, target: Path) -> None:
    try:
        os.symlink(source, target, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass

    if sys.platform == "win32":
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                check=True,
                capture_output=True,
            )
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    shutil.copytree(source, target)
