from __future__ import annotations

import shutil
from pathlib import Path


def install_repo_skills(repo_root: Path, hermes_home: Path, force: bool = False) -> list[Path]:
    source_root = repo_root / "skills"
    target_root = hermes_home / "skills"
    target_root.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for skill_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        destination = target_root / skill_dir.name
        if destination.exists():
            if force:
                shutil.rmtree(destination)
            else:
                continue
        shutil.copytree(skill_dir, destination)
        copied.append(destination)

    config_src = repo_root / "ops" / "hermes" / "config.yaml"
    config_dst = hermes_home / "config.bughunter.yaml"
    shutil.copy2(config_src, config_dst)
    copied.append(config_dst)
    return copied
