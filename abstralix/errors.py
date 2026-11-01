from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console(stderr=True)


@dataclass
class SourceLocation:
    file: str
    line: int
    column: int
    length: int = 1


class AbstralixError(Exception):
    """Base exception for all Abstralix 0.5.0 compiler errors."""

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
        """Renders formatted error panel with source code pointer in terminal."""
        header = Text(f"[{self.code}] ", style="bold red")
        header.append(self.message, style="bold white")

        body_lines = []

        if self.location and self.location.file:
            loc_str = f"  --> {self.location.file}:{self.location.line}:{self.location.column}"
            body_lines.append(Text(loc_str, style="cyan"))

            file_path = Path(self.location.file)
            if file_path.exists():
                try:
                    lines = file_path.read_text(encoding="utf-8").splitlines()
                    line_idx = self.location.line - 1
                    if 0 <= line_idx < len(lines):
                        src_line = lines[line_idx]
                        line_num_str = f"{self.location.line:4d} | "
                        body_lines.append(Text("     |", style="dim cyan"))

                        code_line = Text(line_num_str, style="cyan")
                        code_line.append(src_line, style="white")
                        body_lines.append(code_line)

                        padding = " " * (len(line_num_str) + max(0, self.location.column - 1))
                        pointer = "^" * max(1, self.location.length)
                        pointer_line = Text(padding + pointer, style="bold red")
                        body_lines.append(pointer_line)
                except Exception:
                    pass

        if self.hint:
            body_lines.append(Text(""))
            hint_text = Text("Hint: ", style="bold green")
            hint_text.append(self.hint, style="white")
            body_lines.append(hint_text)

        full_content = Text("\n").join([header] + body_lines)
        console.print(Panel(full_content, border_style="red", title="Abstralix Compiler Error", title_align="left"))


class SyntaxAbxError(AbstralixError):
    """Lexer and Parser errors (SYN_*)."""
    pass


class SemanticAbxError(AbstralixError):
    """Schema, type, and scoping errors (SEM_*)."""
    pass


class TopologyAbxError(AbstralixError):
    """DAG graph, imports, and provider coverage errors (TOP_*)."""
    pass


class RuntimeAbxError(AbstralixError):
    """Runtime, provider network, and sandbox execution errors (RT_*)."""
    pass


class PluginAbxError(AbstralixError):
    """Plugin contract and dynamic loading errors (PLUG_*)."""
    pass
