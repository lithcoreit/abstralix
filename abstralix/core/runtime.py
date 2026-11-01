import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax

from abstralix.config import ConfigManager
from abstralix.core.ir import IRDocument, IRNode
from abstralix.core.sandbox import SandboxManager
from abstralix.errors import RuntimeAbxError
from abstralix.plugins.registry import PluginRegistry

console = Console()


def build_fractal_sequence(max_depth: int) -> List[int]:
    if max_depth <= 0:
        return []
    blocks: Dict[int, List[int]] = {1: [1, 0]}
    for k in range(2, max_depth + 1):
        blocks[k] = [k] + blocks[k - 1] + blocks[k - 1]

    seq: List[int] = []
    for k in range(1, max_depth + 1):
        seq.extend(blocks[k])
    return seq


class RuntimeEngine:
    def __init__(
        self,
        ir: IRDocument,
        config: ConfigManager,
        registry: PluginRegistry,
        sandbox: SandboxManager,
        dev_mode: bool = False,
        verbose: bool = False,
        step_mode: bool = False,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.ir = ir
        self.config = config
        self.registry = registry
        self.sandbox = sandbox
        self.dev_mode = dev_mode
        self.verbose = verbose
        self.step_mode = step_mode
        self.event_callback = event_callback

        self._commit_lock = asyncio.Lock()
        self._review_lock = asyncio.Lock()
        self._log_lock = asyncio.Lock()
        self._completed_count = 0

        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        for p in self.config.providers:
            name = p.get("name", "default")
            limit = max(1, int(p.get("max_concurrency", 1)))
            self._semaphores[name] = asyncio.Semaphore(limit)

    async def _log(self, status: str, message: str, style: str = "white") -> None:
        """Атомарный вывод строки в консоль без наложения параллельных потоков."""
        async with self._log_lock:
            tag = f"[{status}]"
            console.print(f"[{style}]{tag:<8}[/{style}] {message}")

    def _select_provider(self, role: str, complexity: float) -> Dict[str, Any]:
        candidates = [
            p for p in self.config.providers
            if role in p.get("roles", ["code_generation"])
            and float(p.get("min_complexity", 0.0)) <= complexity <= float(p.get("max_complexity", 1.0))
        ]
        if not candidates:
            candidates = [p for p in self.config.providers if role in p.get("roles", [])] or self.config.providers

        candidates.sort(key=lambda x: int(x.get("priority", 10)))
        return candidates[0]

    async def _call_llm(
        self,
        role: str,
        complexity: float,
        messages: List[Dict[str, str]],
        debug_tag: str,
        temperature: float = 0.2,
    ) -> str:
        prov_cfg = self._select_provider(role, complexity)
        prov_name = prov_cfg.get("name", "default")
        adapter_id = prov_cfg.get("adapter", "openai_compatible")
        plugin = self.registry.get_provider(adapter_id)
        sem = self._semaphores[prov_name]

        async with sem:
            if self.verbose:
                await self._log("TRACE", f"LLM request to '{prov_name}' ({debug_tag}, temp={temperature})", style="dim cyan")
            resp = await plugin.send_prompt(
                messages=messages,
                model=prov_cfg.get("model", "local-model"),
                base_url=prov_cfg.get("base_url", "http://localhost:1234/v1"),
                api_key=prov_cfg.get("api_key", "not-needed"),
                temperature=temperature,
            )

        if self.dev_mode:
            log_file = self.sandbox.debug_dir / f"prompt_{debug_tag}.json"
            log_file.write_text(
                json.dumps(
                    {
                        "provider": prov_name,
                        "temperature": temperature,
                        "messages": messages,
                        "response": resp.content,
                        "latency_ms": resp.latency_ms,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        return resp.content

    def _save_to_finetune_dataset(self, messages: List[Dict[str, str]], verified_code: str) -> None:
        dataset_file = self.sandbox.base_dir / "finetune_dataset.jsonl"
        clean_msgs = [
            {"role": m["role"], "content": m["content"].split("\n--- PREVIOUS ATTEMPT FAILED ---")[0]}
            for m in messages
        ]
        clean_msgs.append({"role": "assistant", "content": verified_code})
        entry = json.dumps({"messages": clean_msgs}, ensure_ascii=False)
        with dataset_file.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")

    async def run(self) -> None:
        self.sandbox.sync_master_build(self.ir, self.registry)
        self.ir.save(self.sandbox.ir_path)

        voids = [n for n in self.ir.nodes.values() if n.obj_type == "void"]
        total_voids = len(voids)
        self._completed_count = sum(1 for v in voids if v.status == "DONE")

        worker_counter = 0
        active_tasks: Dict[str, asyncio.Task] = {}

        while True:
            voids = [n for n in self.ir.nodes.values() if n.obj_type == "void"]
            if all(v.status == "DONE" for v in voids):
                break

            ready_voids = [
                v for v in voids
                if v.status == "WAITING"
                and v.id not in active_tasks
                and all(self.ir.nodes[dep_id].status == "DONE" for dep_id in v.dependencies)
            ]

            for v in ready_voids:
                if self.step_mode:
                    Prompt.ask(f"\n[bold yellow][STEP][/bold yellow] Press Enter to compile '{v.id}'")

                v.status = "RUNNING"
                worker_counter += 1
                w_name = f"worker_{worker_counter}"
                task = asyncio.create_task(self._process_void_with_rollback(v, w_name, total_voids))
                active_tasks[v.id] = task

            if not active_tasks:
                pending_ids = [v.id for v in voids if v.status != "DONE"]
                raise RuntimeAbxError(
                    code="RT_DEADLOCK",
                    message=f"Scheduler deadlock: remaining voids cannot proceed: {pending_ids}",
                )

            done_set, _ = await asyncio.wait(
                active_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED,
            )

            for vid, t in list(active_tasks.items()):
                if t in done_set:
                    del active_tasks[vid]
                    t.result()

        for node in self.ir.nodes.values():
            if node.obj_type == "file":
                node.status = "DONE"
        self.sandbox.sync_master_build(self.ir, self.registry)
        self.ir.save(self.sandbox.ir_path)

    async def _process_void_with_rollback(self, void_node: IRNode, worker_name: str, total_count: int) -> None:
        success = await self._execute_void_sessions(void_node, worker_name, total_count)
        if success:
            return

        max_depth = int(void_node.attributes.get("@rollback_depth", 2))
        seq = build_fractal_sequence(max_depth)

        clean_path = void_node.id.strip("/")
        short_id = "/".join(clean_path.split("/")[1:]) if "/" in clean_path else clean_path
        await self._log("ROLLBACK", f"{short_id}: sessions exhausted, cascade depth={max_depth}", style="bold yellow")

        for depth_step in seq:
            if depth_step == 0:
                if await self._execute_void_sessions(void_node, worker_name, total_count):
                    return
            else:
                ancestors = self._get_ancestors_at_depth(void_node.id, depth_step)
                for anc_id in ancestors:
                    anc_node = self.ir.nodes[anc_id]
                    if anc_node.attributes.get("@inside") is not None:
                        continue
                    anc_short = "/".join(anc_id.strip("/").split("/")[1:])
                    await self._log("REGEN", f"Regenerating dependency (depth {depth_step}): {anc_short}", style="dim yellow")
                    await self._execute_void_sessions(anc_node, f"{worker_name}_rb", total_count)

        last_err = void_node.error_history[-1] if void_node.error_history else "Verification failure"
        raise RuntimeAbxError(
            code="RT_ROLLBACK_EXHAUSTED",
            message=f"Unit '{void_node.id}' could not be compiled after exhausting all retries and rollback steps.\nLast error: {last_err}",
            hint="Check task specification in @context or review parent dependencies.",
        )

    def _get_ancestors_at_depth(self, start_void_id: str, target_depth: int) -> List[str]:
        current_layer = [start_void_id]
        for _ in range(target_depth):
            next_layer: List[str] = []
            for vid in current_layer:
                for dep_id in self.ir.nodes[vid].dependencies:
                    if dep_id not in next_layer:
                        next_layer.append(dep_id)
            current_layer = next_layer
        return current_layer

    async def _execute_void_sessions(self, void_node: IRNode, worker_name: str, total_count: int) -> bool:
        start_time = time.perf_counter()
        lang_id = str(void_node.attributes.get("@lang", "python"))
        lang_plugin = self.registry.get_language(lang_id)

        max_sessions = max(1, int(void_node.attributes.get("@max_session", 2)))
        max_tries = max(1, int(void_node.attributes.get("@max_try", 3)))
        judges_count = int(void_node.attributes.get("@judges", 0))
        invariant_attr = void_node.attributes.get("@invariant")

        deps_info = []
        for dep_id in void_node.dependencies:
            dep_node = self.ir.nodes[dep_id]
            deps_info.append(
                {
                    "name": dep_node.name,
                    "in": dep_node.attributes.get("@in", {}),
                    "out": dep_node.attributes.get("@out", {}),
                    "info": dep_node.attributes.get("@info", ""),
                    "code": dep_node.generated_code,
                }
            )

        clean_path = void_node.id.strip("/")
        short_id = "/".join(clean_path.split("/")[1:]) if "/" in clean_path else clean_path

        for session_idx in range(1, max_sessions + 1):
            void_node.sessions_used += 1
            last_error: Optional[str] = None

            if invariant_attr == "auto":
                inv_prompt = lang_plugin.build_auto_invariant_prompt(void_node.name, void_node.attributes)
                tag = f"{void_node.name}_auto_inv_s{session_idx}"
                void_node.auto_invariant_code = await self._call_llm(
                    role="test_generation",
                    complexity=void_node.complexity,
                    messages=inv_prompt,
                    debug_tag=tag,
                    temperature=0.2 + (0.2 * (session_idx - 1)),
                )

            active_invariant = (
                void_node.auto_invariant_code if invariant_attr == "auto" else invariant_attr
            )

            for try_idx in range(1, max_tries + 1):
                void_node.attempts_used += 1
                current_temp = round(min(0.85, 0.2 + 0.18 * (try_idx - 1) + 0.1 * (session_idx - 1)), 2)

                messages = lang_plugin.build_prompt(
                    void_name=void_node.name,
                    attributes=void_node.attributes,
                    dependencies_info=deps_info,
                    error_feedback=last_error,
                )

                tag = f"{void_node.name}_s{session_idx}_t{try_idx}"
                candidate_code = await self._call_llm(
                    role="code_generation",
                    complexity=void_node.complexity,
                    messages=messages,
                    debug_tag=tag,
                    temperature=current_temp,
                )

                # Шаг А: AST синтаксис
                syn_ok, syn_err = lang_plugin.check_syntax(candidate_code, void_node.name)
                if not syn_ok:
                    last_error = syn_err
                    void_node.error_history.append(syn_err or "Syntax error")
                    err_brief = syn_err.splitlines()[0] if syn_err else "Syntax error"
                    await self._log("RETRY", f"{short_id}: try {try_idx}/{max_tries} syntax error ({err_brief[:60]})", style="yellow")
                    continue

                # Шаг Б: Инвариант
                if active_invariant:
                    sandbox_root, rel_file = self.sandbox.prepare_worker_sandbox(
                        worker_name=worker_name,
                        ir=self.ir,
                        registry=self.registry,
                        target_void=void_node,
                        candidate_code=candidate_code,
                    )
                    inv_ok, inv_err = await lang_plugin.run_invariant_test(
                        sandbox_root=sandbox_root,
                        rel_file_path=rel_file,
                        void_name=void_node.name,
                        invariant_code=str(active_invariant),
                    )
                    if not inv_ok:
                        last_error = (
                            f"{inv_err}\n\n"
                            f"Your previous implementation was:\n{candidate_code}\n"
                            f"Analyze the failure carefully and fix the logic."
                        )
                        void_node.error_history.append(inv_err or "Invariant failed")
                        brief = inv_err.splitlines()[-1] if inv_err else "Invariant failed"
                        await self._log("RETRY", f"{short_id}: try {try_idx}/{max_tries} failed invariant ({brief[:60]})", style="yellow")
                        continue

                # Шаг В: Судьи
                if judges_count > 0:
                    judge_ok, judge_err = await self._run_judges(void_node, candidate_code, judges_count)
                    if not judge_ok:
                        last_error = f"{judge_err}\n\nYour code:\n{candidate_code}"
                        void_node.error_history.append(judge_err or "Rejected by judge")
                        await self._log("RETRY", f"{short_id}: judge rejected code", style="yellow")
                        continue

                # Шаг Г: Manual Review
                if void_node.attributes.get("@manual_review") is True:
                    rev_ok, rev_comment = await self._ask_manual_review(void_node, candidate_code)
                    if not rev_ok:
                        last_error = f"Reviewer rejected: {rev_comment}\n\nYour code:\n{candidate_code}"
                        void_node.error_history.append(last_error)
                        await self._log("RETRY", f"{short_id}: rejected by reviewer", style="yellow")
                        continue

                # УСПЕХ
                async with self._commit_lock:
                    void_node.generated_code = candidate_code
                    void_node.status = "DONE"
                    self._completed_count += 1
                    self.sandbox.sync_master_build(self.ir, self.registry)
                    self.ir.save(self.sandbox.ir_path)
                    self._save_to_finetune_dataset(messages, candidate_code)

                    if void_node.attributes.get("@checkpoint") is True:
                        self.sandbox.create_checkpoint(void_node)

                elapsed = round(time.perf_counter() - start_time, 2)
                progress_tag = f"[{self._completed_count}/{total_count}]"
                await self._log("OK", f"{progress_tag} {short_id} ({elapsed}s)", style="bold green")
                return True

        return False

    async def _run_judges(
        self, void_node: IRNode, candidate_code: str, count: int
    ) -> Tuple[bool, Optional[str]]:
        sys_msg = (
            "You are a strict semantic code judge for Abstralix 0.5.0.\n"
            "Verify whether the Python function satisfies the task description (@context).\n"
            "If it satisfies the task, reply starting with 'PASS'.\n"
            "If it fails or has logical flaws, reply starting with 'FAIL:' followed by a short explanation."
        )
        user_msg = (
            f"Task: {void_node.attributes.get('@context')}\n"
            f"Signature: in={void_node.attributes.get('@in')}, out={void_node.attributes.get('@out')}\n\n"
            f"Generated Code:\n{candidate_code}"
        )
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ]
        for j in range(1, count + 1):
            verdict = await self._call_llm(
                role="judging",
                complexity=void_node.complexity,
                messages=messages,
                debug_tag=f"{void_node.name}_judge_{j}",
            )
            if not verdict.strip().upper().startswith("PASS"):
                return False, f"Judge #{j}: {verdict.strip()}"
        return True, None

    async def _ask_manual_review(
        self, void_node: IRNode, candidate_code: str
    ) -> Tuple[bool, Optional[str]]:
        async with self._review_lock:
            console.print()
            console.print(
                Panel(
                    Syntax(candidate_code, "python", theme="monokai", line_numbers=True),
                    title=f"[bold yellow]Manual Review: {void_node.id}[/bold yellow]",
                    border_style="yellow",
                )
            )
            choice = Prompt.ask(
                "Action: [bold green][A]ccept[/bold green] / [bold red][R]eject[/bold red]",
                choices=["a", "r", "A", "R"],
                default="a",
            ).lower()
            if choice == "a":
                return True, None
            comment = Prompt.ask("Feedback for LLM")
            return False, comment