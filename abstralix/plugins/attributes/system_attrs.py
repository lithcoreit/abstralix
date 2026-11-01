from typing import Any
from abstralix.plugins.base.base_attribute import BaseAttributePlugin


class LangAttr(BaseAttributePlugin):
    name = "@lang"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["str"]
    inheritable = True
    default = "python"


class ContextAttr(BaseAttributePlugin):
    name = "@context"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["str"]
    inheritable = True
    default = ""


class InfoAttr(BaseAttributePlugin):
    name = "@info"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["str"]
    inheritable = True
    default = ""


class InAttr(BaseAttributePlugin):
    name = "@in"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["dict"]
    inheritable = True
    default = {}


class OutAttr(BaseAttributePlugin):
    name = "@out"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["dict"]
    inheritable = True
    default = {}


class InsideAttr(BaseAttributePlugin):
    name = "@inside"
    allowed_scopes = ["file", "void"]
    allowed_types = ["str"]
    inheritable = False
    default = None


class UseAttr(BaseAttributePlugin):
    name = "@use"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["list", "str"]
    inheritable = True
    default = []

    def normalize(self, value: Any) -> Any:
        return [value] if isinstance(value, str) else value


class ImportAttr(BaseAttributePlugin):
    name = "@import"
    allowed_scopes = ["file"]
    allowed_types = ["list", "str"]
    inheritable = False
    default = []

    def normalize(self, value: Any) -> Any:
        return [value] if isinstance(value, str) else value


class LibAttr(BaseAttributePlugin):
    name = "@lib"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["list", "str"]
    inheritable = True
    default = []

    def normalize(self, value: Any) -> Any:
        return [value] if isinstance(value, str) else value


class InjectCodeAttr(BaseAttributePlugin):
    name = "@inject_code"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["bool"]
    inheritable = True
    default = False


class InvariantAttr(BaseAttributePlugin):
    name = "@invariant"
    allowed_scopes = ["void"]
    allowed_types = ["str", "keyword:auto"]
    inheritable = False
    default = None


class JudgesAttr(BaseAttributePlugin):
    name = "@judges"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["int"]
    inheritable = True
    default = 0


class MaxTryAttr(BaseAttributePlugin):
    name = "@max_try"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["int"]
    inheritable = True
    default = 3


class MaxSessionAttr(BaseAttributePlugin):
    name = "@max_session"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["int"]
    inheritable = True
    default = 2


class RollbackDepthAttr(BaseAttributePlugin):
    name = "@rollback_depth"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["int"]
    inheritable = True
    default = 2


class CheckpointAttr(BaseAttributePlugin):
    name = "@checkpoint"
    allowed_scopes = ["void"]
    allowed_types = ["bool"]
    inheritable = False
    default = False


class ManualReviewAttr(BaseAttributePlugin):
    name = "@manual_review"
    allowed_scopes = ["folder", "file", "void"]
    allowed_types = ["bool"]
    inheritable = True
    default = False
