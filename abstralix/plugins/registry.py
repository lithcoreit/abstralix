import importlib
import importlib.util
import inspect
import pkgutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from abstralix.errors import PluginAbxError
from abstralix.plugins.base.base_object import BaseObjectPlugin
from abstralix.plugins.base.base_attribute import BaseAttributePlugin
from abstralix.plugins.base.base_type import BaseTypePlugin
from abstralix.plugins.base.base_function import BaseFunctionPlugin
from abstralix.plugins.providers.base import BaseProviderPlugin
from abstralix.plugins.languages.base import BaseLanguagePlugin


class PluginRegistry:
    def __init__(self):
        self.objects: Dict[str, BaseObjectPlugin] = {}
        self.attributes: Dict[str, BaseAttributePlugin] = {}
        self.types: Dict[str, BaseTypePlugin] = {}
        self.functions: Dict[str, BaseFunctionPlugin] = {}
        self.providers: Dict[str, BaseProviderPlugin] = {}
        self.languages: Dict[str, BaseLanguagePlugin] = {}
        self.discover_all()

    def discover_all(self) -> None:
        """Discovers built-in plugins and scans local ./plugins directory if present."""
        import abstralix.plugins.objects as obj_pkg
        import abstralix.plugins.attributes as attr_pkg
        import abstralix.plugins.types as type_pkg
        import abstralix.plugins.functions as fn_pkg
        import abstralix.plugins.providers as prov_pkg
        import abstralix.plugins.languages as lang_pkg

        # 1. Built-in plugins
        self._scan_package(obj_pkg, BaseObjectPlugin, self.register_object)
        self._scan_package(attr_pkg, BaseAttributePlugin, self.register_attribute)
        self._scan_package(type_pkg, BaseTypePlugin, self.register_type)
        self._scan_package(fn_pkg, BaseFunctionPlugin, self.register_function)
        self._scan_package(prov_pkg, BaseProviderPlugin, self.register_provider)
        self._scan_package(lang_pkg, BaseLanguagePlugin, self.register_language)

        # 2. External local plugins from ./plugins directory (Hybrid loading)
        self._scan_external_plugins()

    def _scan_package(self, package, base_cls, register_fn):
        for _, module_name, _ in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                mod = importlib.import_module(module_name)
                for _, cls in inspect.getmembers(mod, inspect.isclass):
                    if issubclass(cls, base_cls) and cls is not base_cls:
                        instance = cls()
                        register_fn(instance)
            except Exception as exc:
                raise PluginAbxError(
                    code="PLUG_HEALTHCHECK_FAILED",
                    message=f"Failed loading plugin in module '{module_name}': {exc}",
                )

    def _scan_external_plugins(self):
        local_plugins_dir = Path.cwd() / "plugins"
        if not local_plugins_dir.exists() or not local_plugins_dir.is_dir():
            return

        category_map = {
            "objects": (BaseObjectPlugin, self.register_object),
            "attributes": (BaseAttributePlugin, self.register_attribute),
            "types": (BaseTypePlugin, self.register_type),
            "functions": (BaseFunctionPlugin, self.register_function),
            "providers": (BaseProviderPlugin, self.register_provider),
            "languages": (BaseLanguagePlugin, self.register_language),
        }

        for folder_name, (base_cls, reg_fn) in category_map.items():
            cat_dir = local_plugins_dir / folder_name
            if cat_dir.exists() and cat_dir.is_dir():
                for py_file in cat_dir.glob("*.py"):
                    if py_file.name.startswith("__"):
                        continue
                    try:
                        spec = importlib.util.spec_from_file_location(f"external_{py_file.stem}", py_file)
                        if spec and spec.loader:
                            mod = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(mod)
                            for _, cls in inspect.getmembers(mod, inspect.isclass):
                                if issubclass(cls, base_cls) and cls is not base_cls:
                                    reg_fn(cls())
                    except Exception as exc:
                        raise PluginAbxError(
                            code="PLUG_HEALTHCHECK_FAILED",
                            message=f"Failed loading external plugin '{py_file}': {exc}",
                        )

    def register_object(self, plugin: BaseObjectPlugin) -> None:
        self.objects[plugin.name] = plugin

    def register_attribute(self, plugin: BaseAttributePlugin) -> None:
        self.attributes[plugin.name] = plugin

    def register_type(self, plugin: BaseTypePlugin) -> None:
        self.types[plugin.name] = plugin

    def register_function(self, plugin: BaseFunctionPlugin) -> None:
        self.functions[plugin.name] = plugin

    def register_provider(self, plugin: BaseProviderPlugin) -> None:
        self.providers[plugin.adapter_id] = plugin

    def register_language(self, plugin: BaseLanguagePlugin) -> None:
        self.languages[plugin.language_id] = plugin

    def get_object(self, name: str) -> BaseObjectPlugin:
        if name not in self.objects:
            raise PluginAbxError("PLUG_NOT_FOUND", f"Object '{name}' not registered")
        return self.objects[name]

    def get_attribute(self, name: str) -> BaseAttributePlugin:
        if name not in self.attributes:
            raise PluginAbxError("PLUG_NOT_FOUND", f"Attribute '{name}' not registered")
        return self.attributes[name]

    def get_language(self, lang_id: str) -> BaseLanguagePlugin:
        if lang_id not in self.languages:
            raise PluginAbxError("PLUG_NOT_FOUND", f"Language '{lang_id}' not registered")
        return self.languages[lang_id]

    def get_provider(self, adapter_id: str) -> BaseProviderPlugin:
        if adapter_id not in self.providers:
            raise PluginAbxError("PLUG_NOT_FOUND", f"Provider adapter '{adapter_id}' not registered")
        return self.providers[adapter_id]

    def check_value_type(self, value: Any, allowed_types: List[str]) -> bool:
        for t in allowed_types:
            if t == "keyword:auto" and value == "auto":
                return True
            if t in self.types and self.types[t].validate(value):
                return True
        return False

    def apply_operator(self, operator: str, base_val: Any, new_val: Any) -> Any:
        if operator == "=" or base_val is None:
            import copy
            return copy.deepcopy(new_val)

        for t_plugin in self.types.values():
            if t_plugin.validate(base_val):
                if operator == "+=":
                    return t_plugin.append(base_val, new_val)
                elif operator == "-=":
                    return t_plugin.remove(base_val, new_val)

        import copy
        return copy.deepcopy(new_val)

    def run_healthcheck(self) -> Dict[str, list]:
        return {
            "objects": list(self.objects.keys()),
            "attributes": list(self.attributes.keys()),
            "types": list(self.types.keys()),
            "functions": list(self.functions.keys()),
            "providers": list(self.providers.keys()),
            "languages": list(self.languages.keys()),
        }


REGISTRY = PluginRegistry()
