import ast
import asyncio
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from abstralix.plugins.languages.base import BaseLanguagePlugin


def _format_py_signature(func_name: str, in_params: Dict[str, str], out_params: Dict[str, str]) -> str:
    args_sig = ", ".join(f"{k}: {v}" for k, v in in_params.items())
    if len(out_params) == 1:
        ret_type = list(out_params.values())[0]
    elif len(out_params) > 1:
        ret_type = "dict"
    else:
        ret_type = "None"
    return f"def {func_name}({args_sig}) -> {ret_type}:"


class PythonLanguagePlugin(BaseLanguagePlugin):
    language_id = "python"

    def build_prompt(
        self,
        void_name: str,
        attributes: Dict[str, Any],
        dependencies_info: List[Dict[str, Any]],
        error_feedback: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        in_params: Dict[str, str] = attributes.get("@in") or {}
        out_params: Dict[str, str] = attributes.get("@out") or {}
        libs: List[str] = attributes.get("@lib") or []
        context_text: str = textwrap.dedent(attributes.get("@context") or "").strip()
        inject_code: bool = bool(attributes.get("@inject_code", False))

        sig_line = _format_py_signature(void_name, in_params, out_params)

        sys_prompt = (
            "You are an isolated Python function generator for Abstralix 5.0.\n"
            "Write ONLY valid Python code for the requested function.\n"
            "Do NOT wrap code in markdown blocks, do NOT add explanations or test calls outside the function.\n"
            f"The function MUST be named '{void_name}' and match the exact parameter names."
        )

        user_lines = [
            f"Target Function Signature:\n{sig_line}\n",
            f"Task Description:\n{context_text}\n",
        ]

        if len(out_params) == 1:
            only_type = list(out_params.values())[0]
            user_lines.append(
                f"Return Rule: Return a single value of type '{only_type}' directly (do NOT wrap it in a dict).\n"
            )
        elif len(out_params) > 1:
            user_lines.append(
                f"Return Rule: Return a Python dict with exact keys: {out_params}\n"
            )

        if libs:
            user_lines.append(f"Allowed / Imported Libraries: {', '.join(libs)}\n")

        if dependencies_info:
            user_lines.append(
                "Available Helper Functions (already imported, call them directly with standard arguments):"
            )
            for dep in dependencies_info:
                dep_sig = _format_py_signature(dep["name"], dep.get("in") or {}, dep.get("out") or {})
                dep_out = dep.get("out") or {}
                ret_note = (
                    f"returns {list(dep_out.values())[0]} directly"
                    if len(dep_out) == 1
                    else f"returns dict {dep_out}"
                )
                user_lines.append(f"- {dep_sig}  # {dep['info']} ({ret_note})")
                if inject_code and dep.get("code"):
                    user_lines.append(f"  Implementation:\n{dep['code']}\n")

        if error_feedback:
            user_lines.append(
                "\n--- PREVIOUS ATTEMPT FAILED ---\n"
                "Your previous code failed verification with the following error. Fix it:\n"
                f"{error_feedback}\n"
            )

        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": "\n".join(user_lines)},
        ]

    def check_syntax(self, code: str, void_name: str) -> Tuple[bool, Optional[str]]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (
                False,
                f"SyntaxError: {exc.msg} at line {exc.lineno}, column {exc.offset}:\n"
                f"{exc.text}\nFull broken code:\n{code}",
            )

        defined_funcs = [
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if void_name not in defined_funcs:
            return (
                False,
                f"NameError: Expected function definition 'def {void_name}(...)', "
                f"but found: {defined_funcs}\nFull broken code:\n{code}",
            )
        return True, None

    def assemble_file(
        self,
        file_attributes: Dict[str, Any],
        voids_code: List[str],
        cross_file_imports: List[Tuple[str, str]],
    ) -> str:
        header_imports: List[str] = []
        seen_imports = set()

        libs = file_attributes.get("@lib") or []
        for lib in libs:
            base_pkg = lib.split(".")[0].strip()
            if base_pkg:
                imp_stmt = f"import {base_pkg}"
                if imp_stmt not in seen_imports:
                    header_imports.append(imp_stmt)
                    seen_imports.add(imp_stmt)

        for mod_path, func_name in cross_file_imports:
            imp_stmt = f"from {mod_path} import {func_name}"
            if imp_stmt not in seen_imports:
                header_imports.append(imp_stmt)
                seen_imports.add(imp_stmt)

        cleaned_voids: List[str] = []
        for code_block in voids_code:
            body_lines: List[str] = []
            for line in code_block.strip().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")) and not line.startswith((" ", "\t")):
                    if stripped not in seen_imports:
                        header_imports.append(stripped)
                        seen_imports.add(stripped)
                else:
                    body_lines.append(line)
            cleaned_voids.append("\n".join(body_lines).strip())

        lines = ["# Generated by Abstralix 5.0"] + header_imports + [""]
        for block in cleaned_voids:
            lines.append(block)
            lines.append("")

        return "\n".join(lines)

    async def run_invariant_test(
        self,
        sandbox_root: Path,
        rel_file_path: Path,
        void_name: str,
        invariant_code: str,
    ) -> Tuple[bool, Optional[str]]:
        runner_file = sandbox_root / f"_abx_test_{void_name}.py"
        module_rel = rel_file_path.with_suffix("")
        module_import = ".".join(module_rel.parts)

        clean_inv = textwrap.dedent(invariant_code).strip()
        indented_inv = "\n".join("    " + line for line in clean_inv.splitlines())

        runner_script = (
            "import sys\n"
            "import inspect\n"
            "import traceback\n"
            f"sys.path.insert(0, {str(sandbox_root)!r})\n"
            f"from {module_import} import {void_name} as _target_fn\n\n"
            "class _CompleteSignal(Exception):\n"
            "    pass\n\n"
            "class _IncompleteSignal(Exception):\n"
            "    pass\n\n"
            "def input(*args, **kwargs):\n"
            "    if len(args) == 1 and not kwargs and isinstance(args[0], dict):\n"
            "        sig_params = set(inspect.signature(_target_fn).parameters.keys())\n"
            "        if set(args[0].keys()).issubset(sig_params) and len(args[0]) > 0:\n"
            "            return _target_fn(**args[0])\n"
            "    return _target_fn(*args, **kwargs)\n\n"
            "def complete():\n"
            "    raise _CompleteSignal()\n\n"
            "def incomplete(reason='Test failed'):\n"
            "    raise _IncompleteSignal(str(reason))\n\n"
            "def _run():\n"
            f"{indented_inv}\n\n"
            "if __name__ == '__main__':\n"
            "    try:\n"
            "        _run()\n"
            "    except _CompleteSignal:\n"
            "        sys.exit(0)\n"
            "    except _IncompleteSignal as e:\n"
            "        print(f'Invariant failed: {e}', file=sys.stderr)\n"
            "        sys.exit(2)\n"
            "    except Exception:\n"
            "        traceback.print_exc(file=sys.stderr)\n"
            "        sys.exit(1)\n"
        )

        runner_file.write_text(runner_script, encoding="utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(runner_file),
                cwd=str(sandbox_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                proc.kill()
                return False, "TimeoutError: Invariant execution exceeded 30 seconds (possible infinite loop)."

            if proc.returncode == 0:
                return True, None

            err_text = stderr.decode("utf-8", errors="replace").strip()
            out_text = stdout.decode("utf-8", errors="replace").strip()
            combined = err_text or out_text or f"Process exited with code {proc.returncode}"
            return False, combined
        finally:
            runner_file.unlink(missing_ok=True)

    def build_auto_invariant_prompt(
        self,
        void_name: str,
        attributes: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        in_params: Dict[str, str] = attributes.get("@in") or {}
        out_params: Dict[str, str] = attributes.get("@out") or {}
        context_text: str = textwrap.dedent(attributes.get("@context") or "").strip()

        sig_line = _format_py_signature(void_name, in_params, out_params)
        example_kwargs = ", ".join(f"{k}=..." for k in in_params.keys())

        sys_prompt = (
            "You are an automated test generator for Abstralix 5.0.\n"
            "Write a short Python invariant test script using ONLY the built-in functions:\n"
            f"- input({example_kwargs}): calls the tested function with normal arguments (do NOT pass a dict wrapper).\n"
            "- incomplete('reason'): fails the test with an explanation.\n"
            "- complete(): marks the test as passed.\n"
            "Return ONLY raw Python statements (no def, no markdown fences)."
        )
        user_prompt = (
            f"Target Function Signature:\n{sig_line}\n"
            f"Specification:\n{context_text}\n\n"
            f"Write 2 assertions calling input({example_kwargs}) and ending with complete()."
        )
        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]