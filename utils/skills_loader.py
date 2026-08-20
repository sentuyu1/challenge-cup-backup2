"""utils/skills_loader.py — 领域 skill 文档加载。

扫描 skills/ 目录，按领域加载解题参考文档与验证知识提示。
skill 文档尚未建成时优雅降级为空字符串（不影响主链路）。
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional


class SkillsLoader:
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else (
            Path(__file__).resolve().parent.parent / "skills")
        self._doc_cache: dict = {}
        self._script_cache: dict = {}

    def _scan_categories(self) -> List[str]:
        if not self.base_path.is_dir():
            return []
        return sorted(p.name for p in self.base_path.iterdir() if p.is_dir())

    def get_skill_document(self, category: str) -> str:
        if category in self._doc_cache:
            return self._doc_cache[category]
        f = self.base_path / category / f"{category}skill.md"
        if f.exists():
            text = f.read_text(encoding="utf-8")
        else:
            text = ""
        self._doc_cache[category] = text
        return text

    def get_validation_script(self, category: str) -> str:
        if category in self._script_cache:
            return self._script_cache[category]
        f = self.base_path / category / f"{category}验证示例.py"
        text = f.read_text(encoding="utf-8") if f.exists() else ""
        self._script_cache[category] = text
        return text

    def list_categories(self) -> List[str]:
        return self._scan_categories()
