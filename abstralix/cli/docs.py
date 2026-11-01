from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

DOCS_USER = """
================================================================================
ABSTRALIX 0.5.0 (ITERATION 5) -- COMPREHENSIVE USER MANUAL
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
    object_type object_name { ... }

There are three built-in structural objects:
1) folder <name> { ... }
   Represents a directory in the filesystem. Can contain other folders and files.
   Example:
       folder backend {
           folder core { ... }
       }

2) file <filename.ext> { ... }
   Represents a physical file on disk. Must contain an explicit literal extension.
   Can contain atomic voids or static raw content via @inside.
   Example:
       file auth_service.py { ... }
       file config.json { @inside = "{\\"active\\": true}" }

3) void <name> { ... }
   The fundamental unit of execution. Represents an isolated function, procedure,
   or logic block. Must reside strictly inside a file object.
   Example:
       void hash_password {
           @in = { password = "str" }
           @out = { hash = "str" }
           @context = "Hash password using sha256."
       }

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
    folder api {
        @lang = "python"
        @lib = ["requests"]
        @use = ["/core/db.py/get_connection"]

        file endpoints.py {
            // Automatically inherits @lang, @lib, and @use
            void fetch_data {
                @lib += ["beautifulsoup4"] // libs: requests + beautifulsoup4
            }
            void offline_worker {
                @use -= ["/core/db.py/get_connection"] // safely removes DB dependency
            }
        }
    }

4. COMPLETE ATTRIBUTE REFERENCE (@)
--------------------------------------------------------------------------------
1) Language & Runtime:
   - @lang (Scopes: folder, file, void | Type: str | Inheritable: Yes)
     Identifies target language plugin (e.g. "python", "typescript", "rust", "go").
     Default: "python".

2) Context & Specification:
   - @context (Scopes: folder, file, void | Type: str | Inheritable: Yes via +=)
     The exact engineering specification (prompt) for the code generator.
   - @info (Scopes: folder, file, void | Type: str | Inheritable: Yes)
     Concise passport describing what this void does. Automatically injected
     into dependent voids calling it via @use.

3) Signature & Static Content:
   - @in (Scopes: folder, file, void | Type: dict | Inheritable: Yes)
     Input parameter names and type annotations: { arg = "type" }.
   - @out (Scopes: folder, file, void | Type: dict | Inheritable: Yes)
     Output/return types: { result = "type" }.
   - @inside (Scopes: file, void | Type: str | Inheritable: No)
     Raw static text. When set on a file, disables AI compilation and writes
     the exact text directly to disk (configs, templates, assets).

4) Modularity & Dependencies:
   - @use (Scopes: folder, file, void | Type: list[str] | Inheritable: Yes)
     Explicit dependencies on other voids. Defines directed graph edges (DAG).
   - @import (Scopes: file | Type: list[str] | Inheritable: No)
     Brings external folders and files into the file's local search scope.
   - @lib (Scopes: folder, file, void | Type: list[str] | Inheritable: Yes)
     Allowed third-party packages and standard library imports.
   - @inject_code (Scopes: folder, file, void | Type: bool | Inheritable: Yes)
     If true, injects full source code of parent dependencies into LLM context.
     Default: false (interfaces only).

5) Verification & Safety:
   - @invariant (Scopes: void | Type: str or 'auto' | Inheritable: No)
     Test script executed inside shadow sandbox.
     If 'auto', LLM test generator constructs assertions automatically.
     If string, executes custom test using input(), complete(), incomplete().
   - @judges (Scopes: folder, file, void | Type: int | Inheritable: Yes)
     Number of independent LLM judges evaluating semantic correctness after tests.
     Default: 0.
   - @manual_review (Scopes: folder, file, void | Type: bool | Inheritable: Yes)
     Pauses pipeline and prompts user to accept/reject generated code with diff.
   - @checkpoint (Scopes: void | Type: bool | Inheritable: No)
     Saves immutable snapshot of project build state upon void completion.
   - @max_try (Scopes: folder, file, void | Type: int | Inheritable: Yes)
     Max retry attempts within a single conversation session. Default: 3.
   - @max_session (Scopes: folder, file, void | Type: int | Inheritable: Yes)
     Max context-clearing restarts when retries fail. Default: 2.
   - @rollback_depth (Scopes: folder, file, void | Type: int | Inheritable: Yes)
     Maximum DAG depth for fractal cascade rollback upon persistent failure. Default: 2.

5. COMPILE-TIME MACROS
--------------------------------------------------------------------------------
To prevent bloated .abx files, inline compile-time functions are provided:
- file("./relative/path.ext")
  Reads external file relative to current .abx file and injects as string.
  Example: @context = file("./specs/auth.md")
  Example: @inside = file("./static/index.html")
- env("VAR_NAME", "optional_default")
  Pulls an environment variable during static compilation.
"""

DOCS_ARCH = """
================================================================================
ABSTRALIX 0.5.0 (ITERATION 5) -- ARCHITECTURE & COMPILER INTERNALS
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
  5) Provider generates code. Dynamic temperature scaling applies on retries:
     temp = min(0.85, 0.2 + 0.18 * (try_idx - 1) + 0.1 * (session_idx - 1)).
  6) Multi-level Verification:
     - Level A: AST syntax check (instant, local).
     - Level B: Sandbox invariant execution in isolated subprocess.
     - Level C: Independent AI Judges (@judges > 0).
     - Level D: Human-in-the-loop approval (@manual_review == true).
  7) Atomic Commit: Verified file is committed into .abx_cache/master_build/,
     the state is saved to project.ir.json, and dependent voids are unlocked.

3. THE FRACTAL CASCADE ROLLBACK ALGORITHM
--------------------------------------------------------------------------------
When an LLM exhausts all @max_session attempts, linear rollback (1 -> 2 -> 3)
destroys valid code because parent modules get only a single chance to adjust.

Abstralix implements a fractal recursive cascade:
Formula:
    Block(0) = [0]
    Block(K) = [K] + Block(K-1) + Block(K-1)
Expansion for depth 2:
    Sequence: [1, 0, 2, 1, 0, 1, 0]

Mechanics:
- If void V fails, depth 1 parents are invalidated and regenerated.
- V attempts compilation again under new parent contracts.
- If it fails again, depth 2 (grandparents) are regenerated.
- Then the entire depth 1 and 0 subsystem is given TWO complete chances to adapt.
- Prevents premature failure and finds self-consistent multi-module solutions.
"""

DOCS_PLUGINS = """
================================================================================
ABSTRALIX 0.5.0 -- EXTENSIBILITY & PLUGIN DEVELOPER GUIDE
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
        name: str                    // e.g. "@timeout"
        allowed_scopes: list[str]    // ["folder", "file", "void"]
        allowed_types: list[str]     // ["int", "float"]
        inheritable: bool = True     // cascades down tree
        default: Any = None

        def normalize(self, value: Any) -> Any:
            return value

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

DOCS_LANGUAGES = """
================================================================================
ABSTRALIX 0.5.0 -- LANGUAGE & FORMAT SUPPORT MATRIX
================================================================================

All 14 language and document plugins are verified with 100% test coverage:

1. PROGRAMMING LANGUAGES:
- Python (.py)       : ast.parse syntax validation; isolated subprocess invariant runner.
- TypeScript (.ts)   : Type definition assembly; Node.js/Bun sandbox runner.
- JavaScript (.js)   : Exported function syntax; Node.js/Bun execution.
- Rust (.rs)         : Brace/token validation; rustc/cargo test integration.
- Go (.go)           : Package and signature assembly; go test harness.
- Java (.java)       : Class and static method assembly; javac integration.
- C# (.cs)           : C# static class method assembly; dotnet test integration.
- C (.c)             : Header and function assembly; gcc/clang syntax check.
- C++ (.cpp)         : Modern C++ function assembly; g++/clang++ integration.
- Assembly (.asm)    : x86-64 NASM procedures with global export and ret instruction.
- Abstralix (.abx)   : Full self-hosting language! Validates generated .abx code
                       using Abstralix's own Lexer and Parser.

2. DOCUMENTATION & DATA FORMATS:
- JSON (.json)       : Structured data generator; validates via strict json.loads.
- Markdown (.md)     : Documentation generator (READMEs, specs, tutorials).
- Text (.txt)        : Plain-text logs, configurations, and raw assets.
"""

DOCS_HISTORY = """
================================================================================
ABSTRALIX -- EVOLUTION & RESEARCH HISTORY
================================================================================

- Iteration 1 - 3 (The Monolithic Generation Trap):
  Explored direct generation of multi-file repositories using single prompts.
  Proved that local and cloud LLMs suffer catastrophic context collapse:
  errors in early files cascade into later modules, making software scale impossible.

- Iteration 4 (The First Void Prototype):
  Introduced atomic units called Voids (^) and Directives (#) with topological DAG sorting.
  Key Limitations of Iteration 4:
  * Cryptic symbol syntax (^, #, >>, <<) created cognitive friction.
  * Inflexible inheritance: directives could only overwrite, not merge or append.
  * Monolithic core: language logic and compiler steps were hardcoded in single files.
  * Linear rollback: single failure in a parent triggered cascading project teardowns.
  * Hardcoded Python bias: other languages could not easily be added.

- Iteration 5 / Version 0.5.0 (The Unified Microkernel Architecture):
  A complete from-scratch reimagining of the compiler:
  * Unified, clean object-attribute syntax: folder, file, void, @attribute.
  * Symmetrical assignment algebra: =, +=, -= with universal inheritance.
  * Pure Microkernel State Machine: zero hardcoded domain logic in core.
  * 6 Modular Plugin Categories: all objects, attributes, types, functions,
    providers, and languages are fully pluggable.
  * Verified 14-language foundation matrix out of the box.
  * Mathematical Fractal Cascade Rollback: sequence [1, 0, 2, 1, 0, 1, 0].
  * Atomic Shadow Sandboxes preventing race conditions in parallel compilation.
  * Built-in Language Server Protocol (abx lsp) and rich developer toolchain.
"""

DOCS_ROADMAP = """
================================================================================
ABSTRALIX -- FUTURE ROADMAP & RESEARCH OBJECTIVES
================================================================================

1. SPECIALIZED MODEL FINE-TUNING (Abstralix-Coder)
- Problem: General-purpose LLMs waste attempts guessing formatting rules.
- Solution: Fine-tune lightweight open weights (Qwen2.5-Coder-7B/14B) using
  Unsloth and QLoRA on verified Abstralix datasets (.abx_cache/finetune_dataset.jsonl).
- Objectives:
  * 1-shot generation of void functions adhering strictly to input/output types.
  * 1-shot self-correction from compiler and test tracebacks.
  * Native understanding of invariant creation (input, complete, incomplete).

2. DISTRIBUTED CLUSTER COMPILATION
- Distribute DAG compilation workloads across LAN nodes and remote GPU instances.

3. VISUAL ARCHITECTURE DESIGNER (No-Code / Low-Code IDE)
- Bi-directional visual node editor: drag-and-drop architectural graphs
  that compile to legal .abx code, and decompile .abx files back into graphs.

4. ECOSYSTEM PACKAGE REGISTRY
- Public hub for importing, versioning, and sharing pre-compiled .abx packages.
"""

DOCS_SPONSOR = """
================================================================================
AUTHOR, CONTACT & SPONSORSHIP
================================================================================

Project: Abstralix (Declarative Architecture & Intent Compiler)
Version: 0.5.0 (Iteration 5 Public Preview)
Author:  LITH::core
Email:   lithcoreit@gmail.com
License: MIT Open Source License

MISSION STATEMENT:
Abstralix is an open-source initiative created by LITH::core to eliminate the
context window barrier in AI software engineering, enabling lightweight local
models to reliably construct vast, mathematically verified software architectures.

HOW TO SUPPORT DEVELOPMENT:
- GitHub Repository: https://github.com/LITHcore/abstralix
- Bug reports, feedback & collaboration: lithcoreit@gmail.com
- Star the repo on GitHub and share with the AI engineering community!
"""

SECTIONS = {
    "user": DOCS_USER,
    "arch": DOCS_ARCH,
    "plugins": DOCS_PLUGINS,
    "languages": DOCS_LANGUAGES,
    "history": DOCS_HISTORY,
    "roadmap": DOCS_ROADMAP,
    "sponsor": DOCS_SPONSOR,
}


def show_docs(topic: str = None):
    """Prints documentation directly to the terminal for smooth mouse scrolling."""
    if topic:
        topic_clean = topic.lower().strip()
        if topic_clean in SECTIONS:
            # Выводим напрямую без вызова внешнего more.com!
            console.print(SECTIONS[topic_clean].strip())
            return
        else:
            console.print(f"[yellow]Unknown documentation topic '{topic}'.[/yellow]\n")

    # Главное меню на чистом английском
    table = Table(title="Abstralix 0.5.0 Documentation Index", header_style="bold cyan", show_lines=False)
    table.add_column("Command", style="bold green", width=22)
    table.add_column("Description", style="white")

    table.add_row("abx docs user", "User Guide: Syntax, Objects, Attributes (@), and Operators")
    table.add_row("abx docs arch", "Architecture: Pipeline, Sandboxes, Reactive IR, Rollback")
    table.add_row("abx docs plugins", "Plugin Developer Guide (Objects, Attributes, Types, Languages)")
    table.add_row("abx docs languages", "Languages Matrix (Python, TS, Rust, Go, Java, C#, ASM...)")
    table.add_row("abx docs history", "Evolution from Iterations 1-4 to Iteration 5 Architecture")
    table.add_row("abx docs roadmap", "Future Plans, Custom Model Fine-Tuning, Distributed DAG")
    table.add_row("abx docs sponsor", "Author (LITH::core), Contact, License, and Support Info")

    console.print(table)
    console.print("\nRun [cyan]abx docs <topic>[/cyan] to view full topic documentation (e.g. [cyan]abx docs user[/cyan]).")