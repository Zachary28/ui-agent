"""Discovery of configuration resources in source and wheel installs."""

from importlib.resources import files
from pathlib import Path


def default_config_root() -> Path:
    return Path(str(files("midscene_ui_agent").joinpath("config")))


def default_skill_lock_path() -> Path:
    return default_config_root() / "skills.lock.json"


__all__ = ["default_config_root", "default_skill_lock_path"]
