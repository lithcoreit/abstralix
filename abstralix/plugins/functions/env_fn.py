import os
from typing import Any, List
from abstralix.plugins.base.base_function import BaseFunctionPlugin
from abstralix.errors import SemanticAbxError


class EnvFunctionPlugin(BaseFunctionPlugin):
    name = "env"

    def execute(self, args: List[Any], file_path: str) -> str:
        if len(args) < 1 or not isinstance(args[0], str):
            raise SemanticAbxError(
                code="SEM_TYPE_MISMATCH",
                message="env() expects environment variable name as string",
            )
        default_val = args[1] if len(args) > 1 else ""
        return os.environ.get(args[0], default_val)
