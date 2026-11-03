from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console(stderr=True)


@dataclass
class SourceLocation:
    file: str
    line: int
    column: int
    length: int = 1


class AbstralixError(Exception):
    """Base exception for all Abstralix compiler errors."""

    def __init__(
        self,
        code: str,
        message: str,
        location: Optional[SourceLocation] = None,
        hint: Optional[str] = None,
    ):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.location = location
        self.hint = hint

    def render(self) -> None:
        """Renders clean, borderless compiler error directly into terminal."""
        console.print(f"\n[bold red]error[{self.code}][/bold red]: [bold white]{self.message}[/bold white]")

        if self.location and self.location.file:
            console.print(f"  [cyan]-->[/cyan] {self.location.file}:{self.location.line}:{self.location.column}")
            file_path = Path(self.location.file)
            if file_path.exists():
                try:
                    lines = file_path.read_text(encoding="utf-8").splitlines()
                    idx = self.location.line - 1
                    if 0 <= idx < len(lines):
                        src_line = lines[idx]
                        console.print(f"   [dim cyan]|[/dim cyan]")
                        console.print(f"{self.location.line:2d} [dim cyan]|[/dim cyan] {src_line}")
                        pad = " " * max(0, self.location.column - 1)
                        ptr = "^" * max(1, self.location.length)
                        console.print(f"   [dim cyan]|[/dim cyan] [bold red]{pad}{ptr}[/bold red]")
                except Exception:
                    pass

        if self.hint:
            console.print(f"  [bold green]hint[/bold green]: {self.hint}")
        console.print()


class SyntaxAbxError(AbstralixError):
    pass


class SemanticAbxError(AbstralixError):
    pass


class TopologyAbxError(AbstralixError):
    pass


class RuntimeAbxError(AbstralixError):
    pass


class PluginAbxError(AbstralixError):
    pass
