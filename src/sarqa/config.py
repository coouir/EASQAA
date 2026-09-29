"""Config loading. Files live in configs/ at the repository root; paths inside are repo-relative."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"


def load_config(name: str = "default") -> dict:
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def repo_path(rel: str | Path) -> Path:
    return REPO_ROOT / rel
