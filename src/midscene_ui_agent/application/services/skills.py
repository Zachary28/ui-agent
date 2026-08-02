from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from ...domain.errors import ErrorCode, UiAgentError


class SkillCatalog:
    paths = {
        "browser": "browser/SKILL.md",
        "computer": "computer-automation/SKILL.md",
        "android": "android-automation/SKILL.md",
        "ios": "ios-automation/SKILL.md",
        "harmony": "harmony-automation/SKILL.md",
        "vitest_e2e": "vitest-midscene-e2e/SKILL.md",
    }

    def __init__(self, skills_root: str | Path):
        self.root = Path(skills_root)

    def relative_paths(self) -> dict[str, str]:
        return self.paths.copy()

    def files(self, platform: str) -> list[str]:
        if platform not in self.paths:
            raise UiAgentError(ErrorCode.SKILL_NOT_FOUND, platform)
        files = [self.paths[platform]]
        if platform == "vitest_e2e":
            files += [
                "vitest-midscene-e2e/references/troubleshooting.md",
                "vitest-midscene-e2e/scripts/clone-boilerplate.sh",
            ]
        return files

    def load(self, platform: str) -> dict[str, Any]:
        path = self.root / self.paths.get(platform, "")
        if not path.is_file():
            raise UiAgentError(ErrorCode.SKILL_NOT_FOUND, str(path))
        text = path.read_text(encoding="utf-8")
        front: dict[str, Any] = {}
        if text.startswith("---"):
            block = text.split("---", 2)[1]
            loaded = yaml.safe_load(block)
            front = loaded if isinstance(loaded, dict) else {}
            front = front or {}
        return {
            "path": str(path),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "frontmatter": front,
            "sections": [x[2:] for x in text.splitlines() if x.startswith("## ")],
        }

    def write_lock(self, path: str | Path) -> None:
        data = {
            key: {
                "files": [
                    {"relative_path": f, "sha256": hashlib.sha256((self.root / f).read_bytes()).hexdigest()}
                    for f in self.files(key)
                ]
            }
            for key in self.paths
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def verify_lock(self, path: str | Path, strict: bool = True) -> bool:
        del strict
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for key in self.paths:
            self._verify_platform_data(data, key)
        return True

    def verify_platform_lock(self, path: str | Path, platform: str) -> bool:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self._verify_platform_data(data, platform)
        return True

    def _verify_platform_data(self, data: dict[str, Any], platform: str) -> None:
        found = {x["relative_path"]: x["sha256"] for x in data.get(platform, {}).get("files", [])}
        for f in self.files(platform):
            skill_file = self.root / f
            if not skill_file.is_file():
                raise UiAgentError(ErrorCode.SKILL_NOT_FOUND, str(skill_file))
            actual = hashlib.sha256(skill_file.read_bytes()).hexdigest()
            if found.get(f) != actual:
                raise UiAgentError(ErrorCode.SKILL_NOT_FOUND, f"skill lock mismatch: {f}")
