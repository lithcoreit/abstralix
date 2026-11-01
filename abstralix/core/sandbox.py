import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from abstralix.core.ir import IRDocument, IRNode
from abstralix.plugins.registry import PluginRegistry


class SandboxManager:
    """Manages master workspace, checkpoints, and isolated shadow sandboxes for parallel workers."""

    def __init__(self, work_dir: Optional[Path] = None):
        self.base_dir = (work_dir or Path.cwd()) / ".abx_cache"
        self.master_dir = self.base_dir / "master_build"
        self.sandboxes_dir = self.base_dir / "sandboxes"
        self.checkpoints_dir = self.base_dir / "checkpoints"
        self.debug_dir = self.base_dir / "debug_artifacts"
        self.ir_path = self.base_dir / "project.ir.json"

    def initialize(self, clean: bool = False) -> None:
        if clean and self.base_dir.exists():
            shutil.rmtree(self.base_dir, ignore_errors=True)
        for d in (self.master_dir, self.sandboxes_dir, self.checkpoints_dir, self.debug_dir):
            d.mkdir(parents=True, exist_ok=True)

    def node_to_rel_path(self, node_id: str) -> Path:
        return Path(*[p for p in node_id.strip("/").split("/") if p])

    def sync_master_build(self, ir: IRDocument, registry: PluginRegistry) -> None:
        self._materialize_tree(self.master_dir, ir, registry)

    def prepare_worker_sandbox(
        self,
        worker_name: str,
        ir: IRDocument,
        registry: PluginRegistry,
        target_void: IRNode,
        candidate_code: str,
    ) -> Tuple[Path, Path]:
        """Creates an isolated shadow replica of the project workspace for test execution."""
        worker_dir = self.sandboxes_dir / worker_name
        if worker_dir.exists():
            shutil.rmtree(worker_dir, ignore_errors=True)
        worker_dir.mkdir(parents=True, exist_ok=True)

        override = {target_void.id: candidate_code}
        self._materialize_tree(worker_dir, ir, registry, code_overrides=override)

        root_folder_name = target_void.id.strip("/").split("/")[0]
        project_root_in_sandbox = worker_dir / root_folder_name

        file_node = ir.nodes[target_void.parent_id]
        full_file_rel = self.node_to_rel_path(file_node.id)
        rel_inside_project = Path(*full_file_rel.parts[1:])

        return project_root_in_sandbox, rel_inside_project

    def _materialize_tree(
        self,
        target_root: Path,
        ir: IRDocument,
        registry: PluginRegistry,
        code_overrides: Optional[Dict[str, str]] = None,
    ) -> None:
        overrides = code_overrides or {}

        for node in ir.nodes.values():
            if node.obj_type == "folder":
                folder_path = target_root / self.node_to_rel_path(node.id)
                folder_path.mkdir(parents=True, exist_ok=True)

            elif node.obj_type == "file":
                file_path = target_root / self.node_to_rel_path(node.id)
                file_path.parent.mkdir(parents=True, exist_ok=True)

                if node.attributes.get("@inside") is not None:
                    file_path.write_text(str(node.attributes["@inside"]), encoding="utf-8")
                    continue

                lang_id = str(node.attributes.get("@lang", "python"))
                lang_plugin = registry.get_language(lang_id)

                voids_code: List[str] = []
                cross_imports: List[Tuple[str, str]] = []

                for child_id in node.children_ids:
                    v_node = ir.nodes[child_id]
                    code_to_use = overrides.get(v_node.id, v_node.generated_code)
                    if code_to_use:
                        voids_code.append(code_to_use)

                    for dep_id in v_node.dependencies:
                        dep_node = ir.nodes[dep_id]
                        if dep_node.parent_id != node.id:
                            dep_file_node = ir.nodes[dep_node.parent_id]
                            dep_rel = self.node_to_rel_path(dep_file_node.id).with_suffix("")
                            mod_parts = dep_rel.parts[1:]
                            mod_str = ".".join(mod_parts)
                            pair = (mod_str, dep_node.name)
                            if pair not in cross_imports:
                                cross_imports.append(pair)

                assembled = lang_plugin.assemble_file(
                    file_attributes=node.attributes,
                    voids_code=voids_code,
                    cross_file_imports=cross_imports,
                )
                file_path.write_text(assembled, encoding="utf-8")

    def create_checkpoint(self, void_node: IRNode) -> Path:
        safe_name = void_node.id.strip("/").replace("/", "_").replace(".", "_")
        chk_dir = self.checkpoints_dir / f"chk_{safe_name}"
        if chk_dir.exists():
            shutil.rmtree(chk_dir, ignore_errors=True)
        shutil.copytree(self.master_dir, chk_dir)
        return chk_dir

    def export_final_build(self, output_dir: Path, ir: IRDocument) -> List[Path]:
        exported: List[Path] = []
        output_dir.mkdir(parents=True, exist_ok=True)

        for root_id in ir.root_ids:
            root_node = ir.nodes[root_id]
            src_dir = self.master_dir / root_node.name
            dst_dir = output_dir / root_node.name
            if dst_dir.exists():
                shutil.rmtree(dst_dir, ignore_errors=True)
            if src_dir.exists():
                shutil.copytree(src_dir, dst_dir)
                exported.append(dst_dir)

        return exported
