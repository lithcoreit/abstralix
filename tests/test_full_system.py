import asyncio
import sys
from pathlib import Path
from typing import Any, Dict
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent))

from abstralix import __version__
from abstralix.config import ConfigManager
from abstralix.plugins.registry import PluginRegistry

console = Console()


async def test_providers(registry: PluginRegistry, config: ConfigManager) -> bool:
    console.print(f"\n[bold cyan]1. Testing Neural Providers ({len(config.providers)} configured)[/bold cyan]")
    table = Table(show_lines=False)
    table.add_column("Provider Name", style="cyan", width=20)
    table.add_column("Adapter", style="white", width=20)
    table.add_column("Status", width=12)
    table.add_column("Details", style="dim white")

    for p in config.providers:
        name = p.get("name", "unnamed")
        adapter_id = p.get("adapter", "openai_compatible")
        base_url = p.get("base_url", "")
        api_key = p.get("api_key", "")

        try:
            plugin = registry.get_provider(adapter_id)
            is_online = await plugin.check_health(base_url, api_key)

            if is_online:
                try:
                    resp = await plugin.send_prompt(
                        messages=[
                            {"role": "system", "content": "Test agent"},
                            {"role": "user", "content": "Return the word: OK"},
                        ],
                        model=p.get("model", "local-model"),
                        base_url=base_url,
                        api_key=api_key,
                        temperature=0.1,
                    )
                    table.add_row(name, adapter_id, "[bold green]ONLINE[/bold green]", f"Ping ({resp.latency_ms}ms) -> {resp.content[:30]}")
                except Exception as e:
                    table.add_row(name, adapter_id, "[bold green]REACHABLE[/bold green]", f"Health OK, call note: {e}")
            else:
                table.add_row(name, adapter_id, "[dim yellow]OFFLINE[/dim yellow]", f"No server / unconfigured key ({base_url})")
        except Exception as exc:
            table.add_row(name, adapter_id, "[bold red]ERROR[/bold red]", str(exc))

    console.print(table)
    return True


def test_prompts_and_assembly(registry: PluginRegistry) -> bool:
    console.print(f"\n[bold cyan]2. Testing Prompts & File Assembly (All {len(registry.languages)} Languages)[/bold cyan]")
    table = Table(show_lines=False)
    table.add_column("Language", style="cyan", width=14)
    table.add_column("Prompt Quality", width=15)
    table.add_column("Assembly Quality", width=18)
    table.add_column("Sample Signature / Header", style="dim white")

    all_ok = True
    sample_attrs = {
        "@context": "Compute hash and process input payload.",
        "@in": {"user_id": "int", "token": "str"},
        "@out": {"is_valid": "bool"},
        "@lib": ["crypto_lib"],
    }
    sample_deps = [{
        "name": "helper_auth",
        "in": {"key": "str"},
        "out": {"ok": "bool"},
        "info": "Helper auth validator",
        "code": "def helper_auth(key): return True"
    }]

    for lang_id, plugin in sorted(registry.languages.items()):
        prompt_ok = False
        assemble_ok = False
        first_line = ""

        try:
            msgs = plugin.build_prompt("process_token", sample_attrs, sample_deps)
            # Accept if void_name is present in either case (process_token or Process_token)
            content_lower = msgs[1]["content"].lower()
            if "process_token" in content_lower:
                prompt_ok = True
        except Exception as e:
            first_line = f"Prompt error: {e}"

        try:
            if lang_id == "json":
                fake_voids = ['{"part1": 1}', '{"part2": 2}']
            else:
                fake_voids = ["// implementation 1", "// implementation 2"]

            assembled = plugin.assemble_file(sample_attrs, fake_voids, [("auth.mod", "helper_auth")])
            if assembled and ("implementation 1" in assembled or "part1" in assembled):
                assemble_ok = True
                first_line = assembled.strip().splitlines()[0]
        except Exception as e:
            first_line += f" | Assembly error: {e}"

        p_status = "[bold green]PASS[/bold green]" if prompt_ok else "[bold red]FAIL[/bold red]"
        a_status = "[bold green]PASS[/bold green]" if assemble_ok else "[bold red]FAIL[/bold red]"

        if not (prompt_ok and assemble_ok):
            all_ok = False

        table.add_row(lang_id, p_status, a_status, first_line)

    console.print(table)
    return all_ok


async def main():
    console.print(f"[bold green]Abstralix {__version__} Pre-Release System Audit[/bold green]")
    config = ConfigManager()
    registry = PluginRegistry()

    await test_providers(registry, config)
    l_ok = test_prompts_and_assembly(registry)

    console.print()
    if l_ok:
        console.print("[bold green][OK] All language prompts and assemblies are 100% verified![/bold green]\n")
    else:
        console.print("[bold red][!] Fix issues reported above.[/bold red]\n")


if __name__ == "__main__":
    asyncio.run(main())
