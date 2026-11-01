import copy
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from abstralix.core.ast_nodes import ObjectBlock, ProgramAST
from abstralix.core.schema import (
    ATTRIBUTE_RULES,
    OBJECT_RULES,
    apply_operator,
    check_value_type,
    normalize_attribute_value,
)
from abstralix.errors import SemanticAbxError


class IRNode(BaseModel):
    id: str
    name: str
    obj_type: str  # "folder", "file", "void"
    parent_id: Optional[str] = None
    children_ids: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)

    # Runtime states: "WAITING", "RUNNING", "DONE", "FAILED"
    status: str = "WAITING"
    complexity: float = 0.0

    # DAG dependency edges
    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)

    # Generation results and attempt tracking
    generated_code: Optional[str] = None
    auto_invariant_code: Optional[str] = None
    attempts_used: int = 0
    sessions_used: int = 0
    error_history: List[str] = Field(default_factory=list)


class IRDocument(BaseModel):
    version: str = "0.5.0"
    source_file: str
    root_ids: List[str] = Field(default_factory=list)
    nodes: Dict[str, IRNode] = Field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "IRDocument":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class IRBuilder:
    """Builds hierarchical Intermediate Representation with universal top-down inheritance."""

    def __init__(self, config_defaults: Optional[Dict[str, Any]] = None):
        self.config_defaults = config_defaults or {}

    def build(self, ast: ProgramAST) -> IRDocument:
        ir = IRDocument(source_file=ast.file_path)

        # Baseline defaults
        root_defaults: Dict[str, Any] = {}
        for attr_name, rule in ATTRIBUTE_RULES.items():
            if attr_name in self.config_defaults:
                root_defaults[attr_name] = copy.deepcopy(self.config_defaults[attr_name])
            else:
                root_defaults[attr_name] = copy.deepcopy(rule.default)

        seen_roots = set()
        for block in ast.root_objects:
            if block.name in seen_roots:
                raise SemanticAbxError(
                    code="SEM_DUPLICATE_IDENTIFIER",
                    message=f"Duplicate root object identifier '{block.name}'",
                    location=block.location,
                )
            seen_roots.add(block.name)
            node_id = self._process_block(
                block=block,
                parent_id=None,
                parent_type="root",
                inherited_attrs=root_defaults,
                ir=ir,
            )
            ir.root_ids.append(node_id)

        return ir

    def _process_block(
        self,
        block: ObjectBlock,
        parent_id: Optional[str],
        parent_type: str,
        inherited_attrs: Dict[str, Any],
        ir: IRDocument,
    ) -> str:
        # 1. Validate object type existence
        if block.obj_type not in OBJECT_RULES:
            raise SemanticAbxError(
                code="SEM_UNKNOWN_OBJECT",
                message=f"Unknown object type '{block.obj_type}'",
                location=block.location,
                hint=f"Allowed object types: {', '.join(OBJECT_RULES.keys())}.",
            )

        obj_rule = OBJECT_RULES[block.obj_type]

        # 2. Validate hierarchy nesting
        if parent_type not in obj_rule.allowed_parents:
            raise SemanticAbxError(
                code="SEM_SCOPE_ERROR",
                message=f"Object '{block.obj_type} {block.name}' cannot be placed inside '{parent_type}'",
                location=block.location,
                hint=f"'{block.obj_type}' is only allowed inside: {', '.join(obj_rule.allowed_parents)}.",
            )

        # 3. Construct unique canonical path ID
        node_id = f"{parent_id}/{block.name}" if parent_id else f"/{block.name}"

        # 4. Cascade inherited attributes
        current_attrs: Dict[str, Any] = {}
        for attr_name, rule in ATTRIBUTE_RULES.items():
            if rule.inheritable and attr_name in inherited_attrs:
                current_attrs[attr_name] = copy.deepcopy(inherited_attrs[attr_name])
            else:
                current_attrs[attr_name] = copy.deepcopy(rule.default)

        # 5. Apply local attribute statements (=, +=, -=)
        for stmt in block.attributes:
            if stmt.name not in ATTRIBUTE_RULES:
                raise SemanticAbxError(
                    code="SEM_UNKNOWN_ATTRIBUTE",
                    message=f"Unknown attribute '{stmt.name}'",
                    location=stmt.location,
                    hint=f"Available registered attributes: {', '.join(ATTRIBUTE_RULES.keys())}.",
                )

            attr_rule = ATTRIBUTE_RULES[stmt.name]

            if block.obj_type not in attr_rule.allowed_scopes:
                raise SemanticAbxError(
                    code="SEM_SCOPE_ERROR",
                    message=f"Attribute '{stmt.name}' is forbidden inside '{block.obj_type}'",
                    location=stmt.location,
                    hint=f"'{stmt.name}' can only be used in: {', '.join(attr_rule.allowed_scopes)}.",
                )

            norm_val = normalize_attribute_value(stmt.name, stmt.value)

            if stmt.operator == "-=" and "dict" in attr_rule.allowed_types and isinstance(norm_val, (list, str)):
                pass
            elif not check_value_type(norm_val, attr_rule.allowed_types):
                raise SemanticAbxError(
                    code="SEM_TYPE_MISMATCH",
                    message=f"Invalid value type for attribute '{stmt.name}': got {type(stmt.value).__name__}",
                    location=stmt.location,
                    hint=f"Expected one of types: {', '.join(attr_rule.allowed_types)}.",
                )

            base_val = current_attrs.get(stmt.name)
            current_attrs[stmt.name] = apply_operator(stmt.operator, base_val, norm_val)

        # 6. Check @inside scope constraints
        if block.obj_type == "file" and current_attrs.get("@inside") is not None and len(block.children) > 0:
            raise SemanticAbxError(
                code="SEM_SCOPE_ERROR",
                message=f"File '{block.name}' contains both static '@inside' content and child 'void' units",
                location=block.location,
                hint="A file with '@inside' is static and cannot contain voids.",
            )

        # 7. Determine initial state
        initial_status = "WAITING"
        gen_code = None

        if block.obj_type == "folder":
            initial_status = "DONE"
        elif block.obj_type == "file":
            if current_attrs.get("@inside") is not None or len(block.children) == 0:
                initial_status = "DONE"
                gen_code = current_attrs.get("@inside") or ""
        elif block.obj_type == "void":
            if current_attrs.get("@inside") is not None:
                initial_status = "DONE"
                gen_code = current_attrs.get("@inside")

        node = IRNode(
            id=node_id,
            name=block.name,
            obj_type=block.obj_type,
            parent_id=parent_id,
            attributes=current_attrs,
            status=initial_status,
            generated_code=gen_code,
        )
        ir.nodes[node_id] = node

        # 8. Recurse into children
        seen_children = set()
        for child in block.children:
            if child.name in seen_children:
                raise SemanticAbxError(
                    code="SEM_DUPLICATE_IDENTIFIER",
                    message=f"Duplicate identifier '{child.name}' inside '{block.obj_type} {block.name}'",
                    location=child.location,
                )
            seen_children.add(child.name)
            child_id = self._process_block(
                block=child,
                parent_id=node_id,
                parent_type=block.obj_type,
                inherited_attrs=current_attrs,
                ir=ir,
            )
            node.children_ids.append(child_id)

        return node_id
