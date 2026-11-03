from rich.console import Console
from rich.table import Table
from abstralix import __version__, __author__, __email__, __repo__
from abstralix.core.schema import ATTRIBUTE_RULES, OBJECT_RULES
from abstralix.plugins.registry import REGISTRY

console = Console()

DOCS_USER = f"""================================================================================
ABSTRALIX {__version__} -- COMPREHENSIVE USER MANUAL
================================================================================

1. CORE PHILOSOPHY & INTENT-DRIVEN DESIGN
--------------------------------------------------------------------------------
Abstralix is a declarative language designed to transform high-level human or
AI architectural intentions into production-ready software systems.

Traditional LLM code generation fails when projects grow large due to context
window saturation, compounding hallucination loops, and architectural drift.
Abstralix solves this by refusing to generate large codebases in one prompt.
Instead:
- The project is broken down into isolated, atomic logic units called "voids".
- Each void acts as a strict black box with explicit inputs and outputs.
- A local or cloud neural network writes code strictly inside this narrow scope.
- A deterministic compilation and verification engine links modules via a DAG,
  executes isolated tests in sandboxes, and commits code only after proof of correctness.

2. SYNTAX GRAMMAR & STRUCTURAL OBJECTS
--------------------------------------------------------------------------------
Every structure block in Abstralix follows a unified grammar:
    object_type object_name {{ ... }}

There are three built-in structural objects:
1) folder <name> {{ ... }}
   Represents a directory in the filesystem. Can contain other folders and files.
   Example:
       folder backend {{
           folder core {{ ... }}
       }}

2) file <filename.ext> {{ ... }}
   Represents a physical file on disk. Must contain an explicit literal extension.
   Can contain atomic voids or static raw content via @inside.
   Example:
       file auth_service.py {{ ... }}
       file config.json {{ @inside = "{{\"active\": true}}" }}

3) void <name> {{ ... }}
   The fundamental unit of execution. Represents an isolated function, procedure,
   or logic block. Must reside strictly inside a file object.
   Example:
       void hash_password {{
           @in = {{ password = "str" }}
           @out = {{ hash = "str" }}
           @context = "Hash password using sha256."
       }}

3. OPERATORS & UNIVERSAL INHERITANCE
--------------------------------------------------------------------------------
Abstralix features a universal top-down inheritance model:
Any attribute declared on a folder or file automatically cascades down to all
nested folders, files, and voids.

Operators:
- Assignment (=):
  Completely overwrites any inherited or default value.
- Append / Merge (+=):
  - Lists: appends new elements while preserving uniqueness.
  - Dicts: merges keys and updates existing values.
  - Strings: appends new text separated by a double newline.
  - Numbers: arithmetic addition.
- Remove / Exclude (-=):
  - Lists: removes specified elements (safe no-op if absent).
  - Dicts: removes specified keys (safe no-op if absent).
  - Strings: removes substring occurrences.
  - Numbers: arithmetic subtraction.

Example of inheritance:
    folder api {{
        @lang = "python"
        @lib = ["requests"]
        @use = ["/core/db.py/get_connection"]

        file endpoints.py {{
            void fetch_data {{
                @lib += ["beautifulsoup4"] // libs: requests + beautifulsoup4
            }}
            void offline_worker {{
                @use -= ["/core/db.py/get_connection"] // safely removes DB dependency
            }}
        }}
    }}

4. COMPILE-TIME MACROS
--------------------------------------------------------------------------------
- file("./relative/path.ext")
  Reads external file relative to current .abx file and injects as string.
  Example: @context = file("./specs/auth.md")
  Example: @inside = file("./static/index.html")
- env("VAR_NAME", "optional_default")
  Pulls an environment variable during static compilation.
"""

DOCS_ARCH = f"""================================================================================
ABSTRALIX {__version__} -- ARCHITECTURE & COMPILER INTERNALS
================================================================================

1. HIGH-LEVEL ARCHITECTURAL DESIGN
--------------------------------------------------------------------------------
Abstralix is structured as an Abstract Microkernel State Machine.
The core compiler contains zero hardcoded domain knowledge about programming
languages, prompts, testing frameworks, or neural network endpoints.
All domain logic is encapsulated into 6 isolated plugin categories.

2. THE TWO-PHASE PIPELINE
--------------------------------------------------------------------------------
Phase 1: Deterministic Static Frontend
  1) Pre-flight Discovery: PluginRegistry scans plugins/ and validates contracts.
  2) Lexer: Converts source .abx into typed Token stream (with file, line, col).
  3) Parser: Builds Abstract Syntax Tree (AST) and evaluates compile-time macros.
  4) Reducer: Computes top-down inheritance for all attributes (=, +=, -=).
  5) Scope Resolver: Processes @import statements and namespace mappings.
  6) DAG Builder: Links @use dependencies into a Directed Acyclic Graph.
  7) Tarjan Cycle Check: Traverses graph to guarantee no recursive deadlocks.
  8) Normalized Complexity:
     Raw score S = len(@context) + 10 * len(@use) + 5 * (len(@in) + len(@out))
     Normalized: Complexity = (S - S_min) / (S_max - S_min) -> [0.0 .. 1.0].
  9) Provider Gap Check: Verifies that every task complexity is covered by
     at least one provider's [min_complexity, max_complexity] window.

Phase 2: Asynchronous Dynamic Runtime
  1) Scheduler initializes task queues: voids with 0 dependencies become READY;
     dependent voids become WAITING.
  2) Resource Allocator dispatches READY voids across concurrency semaphores.
  3) Worker creates a Shadow Sandbox (.abx_cache/sandboxes/worker_N/) containing
     an exact isolated snapshot of the current master build.
  4) Language plugin builds prompt with signatures, context, and dependencies.
  5) Provider generates code with dynamic temperature scaling on retries.
  6) Multi-level Verification:
     - Level A: AST syntax check (instant, local).
     - Level B: Sandbox invariant execution in isolated subprocess.
     - Level C: Independent AI Judges (@judges > 0).
     - Level D: Human-in-the-loop approval (@manual_review == true).
  7) Atomic Commit: Verified file is committed into .abx_cache/master_build/,
     state saved to project.ir.json, and dependent voids unlocked.

3. THE FRACTAL CASCADE ROLLBACK ALGORITHM
--------------------------------------------------------------------------------
When an LLM exhausts all @max_session attempts, linear rollback destroys valid code.
Abstralix implements a fractal recursive cascade:
    Sequence: [1, 0, 2, 1, 0, 1, 0]
Parent modules are given multiple structured adaptation cycles before deep rollbacks.
"""

DOCS_PLUGINS = f"""================================================================================
ABSTRALIX {__version__} -- EXTENSIBILITY & PLUGIN DEVELOPER GUIDE
================================================================================

Abstralix features 6 extensible plugin categories under abstralix/plugins/:

1. OBJECT PLUGINS (plugins/objects/)
Inherit from BaseObjectPlugin:
    class BaseObjectPlugin(ABC):
        name: str
        allowed_parents: list[str]
        can_contain: list[str]
        is_filesystem_node: bool = True

2. ATTRIBUTE PLUGINS (plugins/attributes/)
Inherit from BaseAttributePlugin:
    class BaseAttributePlugin(ABC):
        name: str
        allowed_scopes: list[str]
        allowed_types: list[str]
        inheritable: bool = True
        default: Any = None
        def normalize(self, value: Any) -> Any: return value

3. TYPE PLUGINS (plugins/types/)
Inherit from BaseTypePlugin to handle =, +=, -= algebra:
    class BaseTypePlugin(ABC):
        name: str
        def validate(self, value: Any) -> bool: ...
        def assign(self, base_val: Any, new_val: Any) -> Any: ...
        def append(self, base_val: Any, delta_val: Any) -> Any: ...
        def remove(self, base_val: Any, delta_val: Any) -> Any: ...

4. FUNCTION PLUGINS (plugins/functions/)
Compile-time macros:
    class BaseFunctionPlugin(ABC):
        name: str
        def execute(self, args: list[Any], file_path: str) -> Any: ...

5. PROVIDER PLUGINS (plugins/providers/)
Network adapters connecting to neural engines:
    class BaseProviderPlugin(ABC):
        adapter_id: str
        async def send_prompt(self, messages, model, base_url, api_key, temperature) -> ProviderResponse: ...
        async def check_health(self, base_url, api_key) -> bool: ...

6. LANGUAGE PLUGINS (plugins/languages/)
Target platform compilers and test adapters:
    class BaseLanguagePlugin(ABC):
        language_id: str
        def build_prompt(self, void_name, attributes, dependencies_info, error_feedback) -> list[dict]: ...
        def check_syntax(self, code, void_name) -> tuple[bool, Optional[str]]: ...
        def assemble_file(self, file_attributes, voids_code, cross_file_imports) -> str: ...
        async def run_invariant_test(self, sandbox_root, rel_file_path, void_name, invariant_code) -> tuple[bool, Optional[str]]: ...
"""

DOCS_ROADMAP = f"""================================================================================
ABSTRALIX {__version__} -- ROADMAP & RESEARCH OBJECTIVES
================================================================================

1. SPECIALIZED MODEL FINE-TUNING (Abstralix-Coder)
Fine-tune lightweight open weights (Qwen2.5-Coder-7B/14B) on verified
Abstralix datasets (.abx_cache/finetune_dataset.jsonl) for 1-shot compilation.

2. DISTRIBUTED CLUSTER COMPILATION
Distribute DAG compilation workloads across LAN nodes and remote GPU instances.

3. VISUAL ARCHITECTURE DESIGNER
Bi-directional visual node editor mapping graphs directly to .abx code.
"""

DOCS_SPONSOR = f"""================================================================================
AUTHOR, CONTACT & SPONSORSHIP
================================================================================

Project: Abstralix (Declarative Architecture & Intent Compiler)
Version: {__version__}
Author:  {__author__}
Email:   {__email__}
Repo:    {__repo__}
License: MIT Open Source License

MISSION STATEMENT:
Abstralix is an open-source initiative created by {__author__} to eliminate the
context window barrier in AI software engineering, enabling lightweight local
models to reliably construct vast, mathematically verified software architectures.

HOW TO SUPPORT DEVELOPMENT:
- GitHub Repository: {__repo__}
- Bug reports, feedback & collaboration: {__email__}
- Star the repository on GitHub and share with the AI engineering community!
"""


def show_attributes():
    console.print(f"\n[bold cyan]Abstralix {__version__} -- System Attributes Reference[/bold cyan]\n")
    for name, r in sorted(ATTRIBUTE_RULES.items()):
        console.print(f"  [bold green]{name:<16}[/bold green] Scopes: {', '.join(r.allowed_scopes):<20} Types: {', '.join(r.allowed_types):<18} Inherits: {str(r.inheritable):<5} Default: {r.default!r}")
    console.print('\nUsage: declare inside structural blocks, e.g. @lang = "python", @in = { x = "int" }\n')


def show_objects():
    console.print(f"\n[bold cyan]Abstralix {__version__} -- Structural Objects Reference[/bold cyan]\n")
    for name, o in sorted(OBJECT_RULES.items()):
        contain_s = ", ".join(o.can_contain) if o.can_contain else "None (atomic leaf)"
        console.print(f"  [bold green]{name:<10}[/bold green] Parents: {', '.join(o.allowed_parents):<18} Can Contain: {contain_s}")
    console.print('\nUsage: folder name { ... }, file name.ext { ... }, void name { ... }\n')


def show_languages():
    console.print(f"\n[bold cyan]Abstralix {__version__} -- Supported Languages & Formats[/bold cyan]\n")
    for lang_id, p in sorted(REGISTRY.languages.items()):
        console.print(f"  [bold green]{lang_id:<14}[/bold green] {p.__class__.__name__}")
    console.print("\nUsage: specify via @lang = \"<id>\" at folder, file, or void level.\n")


SECTIONS = {
    "user": DOCS_USER,
    "arch": DOCS_ARCH,
    "plugins": DOCS_PLUGINS,
    "roadmap": DOCS_ROADMAP,
    "sponsor": DOCS_SPONSOR,
}


def show_docs(topic: str = None):
    if not topic:
        console.print(f"  [bold green]abx docs sponsor[/bold green]     Author ({__author__}), Contact & License")
        console.print("  [bold green]abx docs user[/bold green]        Complete User Guide & Syntax Manual")
        console.print("  [bold green]abx docs arch[/bold green]        Compiler Architecture, FSM, DAG & Sandboxes")
        console.print("  [bold green]abx docs attributes[/bold green]  Complete Registered Attributes Reference (@)")
        console.print("  [bold green]abx docs objects[/bold green]     Structural Objects Reference (folder, file, void)")
        console.print("  [bold green]abx docs languages[/bold green]   Matrix of all 14 Supported Languages & Formats")
        console.print("  [bold green]abx docs plugins[/bold green]     Plugin Developer Guide (6 Plugin Categories)")
        console.print("  [bold green]abx docs roadmap[/bold green]     Future Plans & Fine-Tuning Objectives")
        console.print("  [bold green]abx docs sponsor[/bold green]     Author ({__author__}), Contact & License")
        console.print("\nRun [cyan]abx docs <topic>[/cyan] to view details.\n")
        return

    topic_clean = topic.lower().strip()
    if topic_clean == "attributes":
        show_attributes()
    elif topic_clean == "objects":
        show_objects()
    elif topic_clean == "languages":
        show_languages()
    elif topic_clean in SECTIONS:
        console.print(SECTIONS[topic_clean].strip())
        console.print()
    else:
        console.print(f"\n[yellow]Unknown documentation topic '{topic}'.[/yellow]")
        console.print("Run [cyan]abx docs[/cyan] without arguments to see available topics.\n")
