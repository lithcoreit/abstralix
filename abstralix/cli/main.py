import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Optional
import typer
import uvicorn
from rich.console import Console
from rich.prompt import Prompt
from rich.tree import Tree

from abstralix import __version__, __author__, __email__, __repo__
from abstralix.cli.docs import show_docs
from abstralix.config import ConfigManager, DEFAULT_CONFIG
from abstralix.core.dag import DAGResolver
from abstralix.core.ir import IRBuilder, IRDocument
from abstralix.core.lexer import Lexer
from abstralix.core.parser import Parser
from abstralix.core.runtime import RuntimeEngine
from abstralix.core.sandbox import SandboxManager
from abstralix.errors import AbstralixError
from abstralix.lsp.server import AbstralixLanguageServer
from abstralix.plugins.registry import REGISTRY, PluginRegistry

app = typer.Typer(
    name="abx",
    help=f"Abstralix {__version__} - Declarative Architecture & Intent Compiler",
    no_args_is_help=True,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)
config_app = typer.Typer(help="View and modify configuration", rich_markup_mode=None, pretty_exceptions_enable=False)
plugins_app = typer.Typer(help="Inspect installed plugins", rich_markup_mode=None, pretty_exceptions_enable=False)

app.add_typer(config_app, name="config")
app.add_typer(plugins_app, name="plugins")

console = Console()


def _compile_static(
    abx_file: Path,
    config: ConfigManager,
    registry: PluginRegistry,
    save_debug_to: Optional[Path] = None,
) -> IRDocument:
    registry.run_healthcheck()

    if not abx_file.exists():
        console.print(f"[bold red]error[/bold red]: File '{abx_file}' not found.")
        raise typer.Exit(1)

    source = abx_file.read_text(encoding="utf-8")
    tokens = Lexer(source, str(abx_file)).tokenize()
    ast = Parser(tokens, str(abx_file)).parse()
    ir = IRBuilder(config.defaults).build(ast)
    DAGResolver(ir, config.providers).resolve_all()

    if save_debug_to:
        save_debug_to.mkdir(parents=True, exist_ok=True)
        (save_debug_to / "01_tokens.json").write_text(
            json.dumps([repr(t) for t in tokens], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (save_debug_to / "02_ir_resolved.json").write_text(
            ir.model_dump_json(indent=2),
            encoding="utf-8",
        )

    return ir


@app.command()
def version():
    """Show Abstralix version, author, and repository info."""
    console.print(f"\n[bold cyan]Abstralix Compiler[/bold cyan] v[bold green]{__version__}[/bold green]")
    console.print(f"  Author:     [white]{__author__}[/white] <{__email__}>")
    console.print(f"  Repository: [cyan]{__repo__}[/cyan]")
    console.print(f"  Concept:    [dim]Isolated Neural Units & Deterministic DAG Assembly[/dim]\n")


@app.command()
def init(project_name: str = typer.Argument("demo_project", help="Root folder identifier")):
    """Create a starter .abx file and configuration in current directory."""
    abx_path = Path(f"{project_name}.abx")
    cfg_path = Path("abx.config.json")

    if not cfg_path.exists():
        cfg_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        console.print("[OK] Created abx.config.json")

    sample_abx = (
        f"// Project architecture definition\n"
        f"folder {project_name} {{\n"
        f'    @lang = "python"\n'
        f"    @max_try = 3\n\n"
        f"    file math_utils.py {{\n"
        f'        @info = "Basic mathematical helper routines"\n\n'
        f"        void calc_square {{\n"
        f'            @info = "Returns the square of integer x"\n'
        f'            @in = {{ x = "int" }}\n'
        f'            @out = {{ result = "int" }}\n'
        f'            @context = "Return x multiplied by x."\n'
        f'            @invariant = "if input(x=4) != 16: incomplete(\'4*4 must be 16\')\\ncomplete()"\n'
        f"        }}\n"
        f"    }}\n"
        f"}}\n"
    )
    abx_path.write_text(sample_abx, encoding="utf-8")
    console.print(f"[OK] Initialized architecture: {abx_path}")


@app.command()
def check(
    entrypoint: Path = typer.Argument(..., help="Path to .abx file"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Run static validation (Syntax, Schema, DAG cycles, Providers) with 0 LLM cost."""
    try:
        cfg = ConfigManager(config_file)
        ir = _compile_static(entrypoint, cfg, REGISTRY)

        voids = [n for n in ir.nodes.values() if n.obj_type == "void"]
        files = [n for n in ir.nodes.values() if n.obj_type == "file"]
        folders = [n for n in ir.nodes.values() if n.obj_type == "folder"]

        console.print(f"[OK] {entrypoint.name} is valid ({len(folders)} folders, {len(files)} files, {len(voids)} voids).")
    except AbstralixError as err:
        err.render()
        raise typer.Exit(1)


@app.command()
def inspect(
    entrypoint: Path = typer.Argument(..., help="Path to .abx file"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Inspect project hierarchy, dependencies, and normalized complexity."""
    try:
        cfg = ConfigManager(config_file)
        ir = _compile_static(entrypoint, cfg, REGISTRY)

        tree = Tree(f"[bold cyan]{entrypoint.name}[/bold cyan]")

        def add_nodes(parent_tree: Tree, node_id: str):
            node = ir.nodes[node_id]
            tag = f"[{node.obj_type.upper()}]"
            label = f"[dim]{tag:<8}[/dim] {node.name}"
            if node.obj_type == "void":
                label += f" [dim](complexity={node.complexity:.2f})[/dim]"
            branch = parent_tree.add(label)
            for cid in node.children_ids:
                add_nodes(branch, cid)

        for rid in ir.root_ids:
            add_nodes(tree, rid)

        console.print(tree)
    except AbstralixError as err:
        err.render()
        raise typer.Exit(1)


@app.command()
def build(
    entrypoint: Path = typer.Argument(..., help="Path to .abx file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Target output directory"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c"),
    clean: bool = typer.Option(False, "--clean", help="Wipe cache and rebuild"),
    resume: bool = typer.Option(False, "--resume", help="Resume from cached state"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed LLM requests and traces"),
    step: bool = typer.Option(False, "--step", help="Step-by-step confirmation"),
):
    """Compile architecture into working code with automated sandboxed testing."""
    try:
        cfg = ConfigManager(config_file)
        sandbox = SandboxManager()

        out_dir = output or Path(cfg.default_output)

        if sandbox.ir_path.exists() and not clean and not resume:
            choice = Prompt.ask(
                "Cached build found. [R]esume or [C]lean rebuild?",
                choices=["r", "c", "R", "C"],
                default="r",
            ).lower()
            if choice == "c":
                clean = True
            else:
                resume = True

        sandbox.initialize(clean=clean)

        if resume and sandbox.ir_path.exists():
            ir = IRDocument.load(sandbox.ir_path)
            for n in ir.nodes.values():
                if n.obj_type == "void" and n.status != "DONE":
                    n.status = "WAITING"
        else:
            ir = _compile_static(entrypoint, cfg, REGISTRY, save_debug_to=sandbox.debug_dir if cfg.dev_mode else None)

        voids = [n for n in ir.nodes.values() if n.obj_type == "void"]
        console.print(f"[BUILD] Compiling {entrypoint.name} ({len(voids)} units, target: {out_dir})")

        engine = RuntimeEngine(
            ir=ir,
            config=cfg,
            registry=REGISTRY,
            sandbox=sandbox,
            dev_mode=cfg.dev_mode,
            verbose=verbose,
            step_mode=step,
        )

        asyncio.run(engine.run())
        exported = sandbox.export_final_build(out_dir, ir)

        console.print(f"[OK] Build succeeded. Exported to: {', '.join(str(p) for p in exported)}")
    except AbstralixError as err:
        err.render()
        raise typer.Exit(1)


@app.command()
def doctor(config_file: Optional[Path] = typer.Option(None, "--config", "-c")):
    """Diagnose environment and LLM providers."""
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"  [OK] Python: {py_ver}")
    hc = REGISTRY.run_healthcheck()
    console.print(f"  [OK] Plugins: {len(hc['providers'])} providers, {len(hc['languages'])} languages")

    sandbox = SandboxManager()
    sandbox.initialize(clean=False)
    console.print(f"  [OK] Cache: {sandbox.base_dir}")

    cfg = ConfigManager(config_file)
    for p in cfg.providers:
        p_name = p.get("name", "unknown")
        adapter_id = p.get("adapter", "openai_compatible")
        base_url = p.get("base_url", "")
        api_key = p.get("api_key", "")
        plugin = REGISTRY.get_provider(adapter_id)
        online = asyncio.run(plugin.check_health(base_url, api_key))
        if online:
            console.print(f"  [OK] Provider '{p_name}': ONLINE ({base_url})")
        else:
            console.print(f"  [WARN] Provider '{p_name}': OFFLINE ({base_url})")


@app.command()
def docs(
    topic: Optional[str] = typer.Argument(
        None,
        help="Documentation topic: user, arch, attributes, objects, languages, plugins, roadmap, sponsor",
    )
):
    """Read documentation, architecture spec, and system reference."""
    show_docs(topic)


@app.command()
def lsp():
    """Start Language Server Protocol (LSP) daemon over stdio for editors."""
    server = AbstralixLanguageServer()
    server.run()


@app.command()
def clean():
    """Remove .abx_cache workspace."""
    cache_dir = Path(".abx_cache")
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
        console.print("[OK] Cache cleaned.")
    else:
        console.print("[OK] Cache is already clean.")


@config_app.command("show")
def config_show():
    """Display active configuration."""
    cfg = ConfigManager()
    console.print_json(data=cfg.data)


@config_app.command("set")
def config_set(key: str, value: str):
    """Modify a configuration parameter."""
    cfg = ConfigManager()
    new_val = cfg.set_key(key, value)
    console.print(f"[OK] {key} = {new_val!r}")


@plugins_app.command("list")
def plugins_list():
    """List loaded plugins across all 6 categories (borderless view)."""
    categories = [
        ("Object", REGISTRY.objects),
        ("Attribute", REGISTRY.attributes),
        ("Type", REGISTRY.types),
        ("Function", REGISTRY.functions),
        ("Provider", REGISTRY.providers),
        ("Language", REGISTRY.languages),
    ]

    console.print(f"\n[bold cyan]Installed Abstralix {__version__} Plugins[/bold cyan]\n")
    for cat_name, registry_dict in categories:
        for k, v in sorted(registry_dict.items()):
            console.print(f"  [cyan]{cat_name:<12}[/cyan] [bold white]{str(k):<22}[/bold white] [dim green]{v.__class__.__name__}[/dim green]")
    console.print()


if __name__ == "__main__":
    app()
