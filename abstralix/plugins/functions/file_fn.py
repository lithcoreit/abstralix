from pathlib import Path
from typing import Any, List
from abstralix.plugins.base.base_function import BaseFunctionPlugin
from abstralix.errors import SemanticAbxError


class FileFunctionPlugin(BaseFunctionPlugin):
    name = "file"

    def execute(self, args: List[Any], file_path: str) -> str:
        if len(args) != 1 or not isinstance(args[0], str):
            raise SemanticAbxError(
                code="SEM_TYPE_MISMATCH",
                message="file() expects exactly 1 string argument (file path)",
            )
        base_dir = Path(file_path).parent if file_path != "<memory>" else Path.cwd()
        target = (base_dir / args[0]).resolve()
        if not target.exists():
            raise SemanticAbxError(
                code="SEM_FILE_NOT_FOUND",
                message=f"External file not found: '{target}'",
                hint="Check the path inside file(\"...\") relative to the .abx file.",
            )
        return target.read_text(encoding="utf-8")
