import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from abstralix.plugins.languages.base import BaseLanguagePlugin


class JsonFormatPlugin(BaseLanguagePlugin):
    language_id = "json"

    def build_prompt(
        self, void_name: str, attributes: Dict[str, Any], dependencies_info: List[Dict[str, Any]], error_feedback: Optional[str] = None
    ) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": "Generate valid JSON without markdown fences."},
            {"role": "user", "content": f"Generate JSON for: {attributes.get('@context')}"},
        ]

    def check_syntax(self, code: str, void_name: str) -> Tuple[bool, Optional[str]]:
        try:
            json.loads(code.strip())
            return True, None
        except Exception as exc:
            return False, f"Invalid JSON syntax: {exc}"

    def assemble_file(
        self, file_attributes: Dict[str, Any], voids_code: List[str], cross_file_imports: List[Tuple[str, str]]
    ) -> str:
        return voids_code[0].strip() if voids_code else "{}"

    async def run_invariant_test(
        self, sandbox_root: Path, rel_file_path: Path, void_name: str, invariant_code: str
    ) -> Tuple[bool, Optional[str]]:
        return True, None

    def build_auto_invariant_prompt(self, void_name: str, attributes: Dict[str, Any]) -> List[Dict[str, str]]:
        return [{"role": "system", "content": "Test JSON"}, {"role": "user", "content": f"Test {void_name}"}]


class MarkdownFormatPlugin(BaseLanguagePlugin):
    language_id = "markdown"

    def build_prompt(
        self, void_name: str, attributes: Dict[str, Any], dependencies_info: List[Dict[str, Any]], error_feedback: Optional[str] = None
    ) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": "Write clean Markdown documentation."},
            {"role": "user", "content": f"Topic: {attributes.get('@context')}"},
        ]

    def check_syntax(self, code: str, void_name: str) -> Tuple[bool, Optional[str]]:
        if not code.strip():
            return False, "Generated documentation is empty"
        return True, None

    def assemble_file(
        self, file_attributes: Dict[str, Any], voids_code: List[str], cross_file_imports: List[Tuple[str, str]]
    ) -> str:
        return "\n\n".join(v.strip() for v in voids_code)

    async def run_invariant_test(
        self, sandbox_root: Path, rel_file_path: Path, void_name: str, invariant_code: str
    ) -> Tuple[bool, Optional[str]]:
        return True, None

    def build_auto_invariant_prompt(self, void_name: str, attributes: Dict[str, Any]) -> List[Dict[str, str]]:
        return [{"role": "system", "content": "Test MD"}, {"role": "user", "content": f"Test {void_name}"}]


class TextFormatPlugin(MarkdownFormatPlugin):
    language_id = "text"
