from typing import Any, Dict, List, Optional
from abstralix.core.ir import IRDocument, IRNode
from abstralix.errors import TopologyAbxError


class DAGResolver:
    """Resolves modular references, validates directed acyclic topology, and computes complexity."""

    def __init__(self, ir: IRDocument, providers: Optional[List[Dict[str, Any]]] = None):
        self.ir = ir
        self.providers = providers or []

    def resolve_all(self) -> None:
        self._validate_imports()
        self._build_dependencies()
        self._detect_cycles()
        self._calculate_complexity()
        if self.providers:
            self._check_provider_coverage()

    def _validate_imports(self) -> None:
        for node in self.ir.nodes.values():
            if node.obj_type == "file":
                imports = node.attributes.get("@import") or []
                for imp_path in imports:
                    norm_path = imp_path if imp_path.startswith("/") else f"/{imp_path}"
                    if norm_path not in self.ir.nodes:
                        raise TopologyAbxError(
                            code="TOP_INVALID_IMPORT_PATH",
                            message=f"File '{node.id}' imports non-existent path '{imp_path}'",
                            hint="Specify valid absolute path from root folder, e.g. '/project/src/utils.py'.",
                        )

    def _build_dependencies(self) -> None:
        for node in self.ir.nodes.values():
            node.dependencies.clear()
            node.dependents.clear()

        for node in self.ir.nodes.values():
            if node.obj_type != "void":
                continue

            raw_uses = node.attributes.get("@use") or []
            for ref in raw_uses:
                target_id = self._resolve_void_reference(node, ref)
                # Skip inherited self-references
                if target_id == node.id:
                    continue
                if target_id not in node.dependencies:
                    node.dependencies.append(target_id)
                target_node = self.ir.nodes[target_id]
                if node.id not in target_node.dependents:
                    target_node.dependents.append(node.id)

    def _resolve_void_reference(self, from_void: IRNode, ref: str) -> str:
        # 1. Absolute root path
        if ref.startswith("/"):
            if ref in self.ir.nodes and self.ir.nodes[ref].obj_type == "void":
                return ref
            raise TopologyAbxError(
                code="TOP_UNRESOLVED_REFERENCE",
                message=f"Void '{from_void.id}' references non-existent absolute void '{ref}'",
            )

        parent_file = self.ir.nodes.get(from_void.parent_id or "")
        if parent_file:
            # 2. Local sibling within same file
            same_file_candidate = f"{parent_file.id}/{ref}"
            if same_file_candidate in self.ir.nodes and self.ir.nodes[same_file_candidate].obj_type == "void":
                return same_file_candidate

            # 3. Sibling file within same folder
            if parent_file.parent_id:
                same_folder_candidate = f"{parent_file.parent_id}/{ref}"
                if same_folder_candidate in self.ir.nodes and self.ir.nodes[same_folder_candidate].obj_type == "void":
                    return same_folder_candidate

            # 4. Resolved via file's @import statements
            imports = parent_file.attributes.get("@import") or []
            for imp in imports:
                norm_imp = imp if imp.startswith("/") else f"/{imp}"
                imp_node = self.ir.nodes.get(norm_imp)
                if not imp_node:
                    continue
                if imp_node.obj_type == "void" and imp_node.name == ref:
                    return imp_node.id
                candidate = f"{imp_node.id}/{ref}"
                if candidate in self.ir.nodes and self.ir.nodes[candidate].obj_type == "void":
                    return candidate

        # 5. Project-wide unique short name lookup
        matches = [
            n.id for n in self.ir.nodes.values()
            if n.obj_type == "void" and (n.name == ref or n.id.endswith(f"/{ref}"))
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise TopologyAbxError(
                code="TOP_AMBIGUOUS_PATH",
                message=f"Ambiguous reference '{ref}' in '{from_void.id}'. Matches: {', '.join(matches)}",
                hint="Disambiguate reference using @import or an absolute path starting with '/'.",
            )

        raise TopologyAbxError(
            code="TOP_UNRESOLVED_REFERENCE",
            message=f"Could not resolve void reference '{ref}' in '{from_void.id}'",
            hint="Check spelling or declare target module in @import.",
        )

    def _detect_cycles(self) -> None:
        state: Dict[str, int] = {nid: 0 for nid, n in self.ir.nodes.items() if n.obj_type == "void"}
        path_stack: List[str] = []

        def dfs(curr_id: str) -> None:
            state[curr_id] = 1
            path_stack.append(curr_id)

            for dep_id in self.ir.nodes[curr_id].dependencies:
                dep_state = state.get(dep_id, 0)
                if dep_state == 1:
                    cycle_start = path_stack.index(dep_id)
                    cycle_chain = " -> ".join(path_stack[cycle_start:] + [dep_id])
                    raise TopologyAbxError(
                        code="TOP_CYCLIC_DEPENDENCY",
                        message=f"Cyclic dependency detected in @use graph: {cycle_chain}",
                        hint="Eliminate circular dependencies so voids form a directed acyclic graph.",
                    )
                elif dep_state == 0:
                    dfs(dep_id)

            path_stack.pop()
            state[curr_id] = 2

        for void_id in list(state.keys()):
            if state[void_id] == 0:
                dfs(void_id)

    def _calculate_complexity(self) -> None:
        voids = [n for n in self.ir.nodes.values() if n.obj_type == "void"]
        if not voids:
            return

        raw_scores: Dict[str, float] = {}
        for v in voids:
            ctx_len = len(v.attributes.get("@context") or "")
            use_cnt = len(v.dependencies)
            in_cnt = len(v.attributes.get("@in") or {})
            out_cnt = len(v.attributes.get("@out") or {})
            raw_scores[v.id] = float(ctx_len + (10 * use_cnt) + (5 * (in_cnt + out_cnt)))

        min_s = min(raw_scores.values())
        max_s = max(raw_scores.values())

        for v in voids:
            if max_s == min_s:
                v.complexity = 0.0
            else:
                v.complexity = round((raw_scores[v.id] - min_s) / (max_s - min_s), 4)

    def _check_provider_coverage(self) -> None:
        gen_providers = [
            p for p in self.providers
            if "code_generation" in p.get("roles", ["code_generation"])
        ]
        if not gen_providers:
            raise TopologyAbxError(
                code="TOP_PROVIDER_GAP_ERROR",
                message="No providers with 'code_generation' role configured in abx.config.json",
            )

        for node in self.ir.nodes.values():
            if node.obj_type != "void" or node.status == "DONE":
                continue

            c = node.complexity
            covered = any(
                float(p.get("min_complexity", 0.0)) <= c <= float(p.get("max_complexity", 1.0))
                for p in gen_providers
            )
            if not covered:
                ranges_str = ", ".join(
                    f"{p.get('name')}[{p.get('min_complexity', 0.0)}..{p.get('max_complexity', 1.0)}]"
                    for p in gen_providers
                )
                raise TopologyAbxError(
                    code="TOP_PROVIDER_GAP_ERROR",
                    message=f"Void '{node.id}' complexity ({c}) is uncovered by configured providers ({ranges_str})",
                    hint="Adjust provider complexity ranges in abx.config.json to cover [0.0 .. 1.0].",
                )
