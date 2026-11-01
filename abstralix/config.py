import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from abstralix.errors import RuntimeAbxError

DEFAULT_CONFIG: Dict[str, Any] = {
    "settings": {
        "dev_mode": False,
        "default_output": "./build",
    },
    "defaults": {
        "@max_try": 3,
        "@max_session": 2,
        "@judges": 0,
        "@rollback_depth": 2,
    },
    "providers": [
        {
            "name": "local_lm_studio",
            "adapter": "openai_compatible",
            "base_url": "http://localhost:1234/v1",
            "api_key": "not-needed",
            "model": "local-model",
            "roles": ["code_generation", "test_generation", "judging"],
            "min_complexity": 0.0,
            "max_complexity": 1.0,
            "priority": 1,
            "max_concurrency": 1,
        }
    ],
}


class ConfigManager:
    """Manages project configuration, defaults, and neural provider pool."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("abx.config.json")
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return json.loads(json.dumps(DEFAULT_CONFIG))
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeAbxError(
                code="RT_CONFIG_ERROR",
                message=f"Failed parsing configuration file '{self.config_path}': {exc}",
                hint="Run 'abx config init' to reset configuration to defaults.",
            )

    def save(self) -> None:
        self.config_path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def dev_mode(self) -> bool:
        return bool(self.data.get("settings", {}).get("dev_mode", False))

    @property
    def default_output(self) -> str:
        return str(self.data.get("settings", {}).get("default_output", "./build"))

    @property
    def defaults(self) -> Dict[str, Any]:
        return dict(self.data.get("defaults", {}))

    @property
    def providers(self) -> List[Dict[str, Any]]:
        return list(self.data.get("providers", []))

    def get_key(self, dotted_key: str) -> Any:
        parts = dotted_key.split(".")
        curr: Any = self.data
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                raise KeyError(f"Configuration key '{dotted_key}' not found")
        return curr

    def set_key(self, dotted_key: str, raw_val: str) -> Any:
        parts = dotted_key.split(".")
        curr: Any = self.data
        for p in parts[:-1]:
            if p not in curr or not isinstance(curr[p], dict):
                curr[p] = {}
            curr = curr[p]

        # Automatic type coercion
        val: Any = raw_val
        if raw_val.lower() == "true":
            val = True
        elif raw_val.lower() == "false":
            val = False
        else:
            try:
                val = int(raw_val)
            except ValueError:
                try:
                    val = float(raw_val)
                except ValueError:
                    val = raw_val

        curr[parts[-1]] = val
        self.save()
        return val
