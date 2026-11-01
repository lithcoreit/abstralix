from dataclasses import dataclass, field
from typing import Any, List
from abstralix.errors import SourceLocation


@dataclass
class AttributeStmt:
    """Attribute assignment statement: @name = value (or +=, -=)."""
    name: str
    operator: str  # "=", "+=", "-="
    value: Any
    location: SourceLocation


@dataclass
class ObjectBlock:
    """Structural block: folder name { ... }, file name.ext { ... }, void name { ... }."""
    obj_type: str  # "folder", "file", "void"
    name: str
    location: SourceLocation
    attributes: List[AttributeStmt] = field(default_factory=list)
    children: List["ObjectBlock"] = field(default_factory=list)


@dataclass
class ProgramAST:
    """Root syntax tree of the compiled .abx file."""
    file_path: str
    root_objects: List[ObjectBlock] = field(default_factory=list)
