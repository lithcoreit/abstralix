<div align="center">

<img src="logo.png" alt="Abstralix Logo" width="128" height="128" />

# Abstralix

**Declarative Architecture & Intent Compiler for Large-Scale AI Software Engineering**

[![Version](https://img.shields.io/badge/version-0.5.1--preview-blueviolet.svg)](https://github.com/lithcoreit/abstralix)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Languages](https://img.shields.io/badge/languages-14%20verified-green.svg)](https://github.com/lithcoreit/abstralix)
[![Author](https://img.shields.io/badge/author-LITH%3A%3Acore-purple.svg)](mailto:lithcoreit@gmail.com)

</div>

---

> **AI Development Advisory & Disclaimer:**  
> **Notice:** This project was co-engineered and implemented with the active assistance of Artificial Intelligence. While the core deterministic compiler architecture, type system, DAG resolver, and test sandboxes have undergone verification, this is an experimental public alpha preview (`v0.5.1`). Review generated code, execute tests inside isolated environments, and use with appropriate engineering caution.

---

## Overview & Philosophy

### Context Saturation in LLM Code Generation
Modern Large Language Models fail when attempting to write real, multi-file software projects in a single prompt. They suffer from:
1. **Context Saturation:** Architectures and multiple files quickly exceed attention limits.
2. **Cascading Hallucinations:** A single bug early on snowballs into catastrophic architectural drift.
3. **Loss of Focus:** Balancing database models, APIs, and business logic simultaneously degrades code quality.

### The Abstralix Solution: The "Void" Paradigm
Abstralix completely abandons generating whole projects at once:
- **Atomic Decomposition:** Projects are modeled as trees of folders, physical files, and atomic logic units called **"voids"** (isolated black boxes with explicit `@in` and `@out` signatures).
- **Hyper-Localized Context:** A neural model writes code strictly inside one void at a time, completely unaware of global project clutter.
- **Deterministic DAG Assembly:** A mathematical compiler links modules through directed graphs, mounts them into **Shadow Sandboxes**, executes automated invariant tests (`@invariant`), and only commits code upon proof of correctness.
- **Fractal Cascade Rollback:** If a void hits a logical dead-end, an intelligent fractal rollback sequence (`[1, 0, 2, 1, 0, 1, 0]`) regenerates ancestor dependencies to dynamically discover consistent architectural interfaces.

---

## Key Architectural Features

- **Declarative `.abx` Syntax:** Minimalist grammar (`folder`, `file`, `void`, `@attribute`).
- **Universal Inheritance Algebra:** Attributes cascade downwards with `=`, `+=`, and `-=` operators.
- **14 Verified Languages & Formats Out-of-the-Box:**
  - *Systems & Backends:* Python, TypeScript, JavaScript, Rust, Go, Java, C#, C, C++, x86-64 Assembly (NASM).
  - *Self-Hosting:* Native **Abstralix (`.abx`)** compilation.
  - *Data & Docs:* JSON, Markdown, Plain Text.
- **Shadow Sandboxes:** Race-condition-free parallel compilation in isolated workspaces (`.abx_cache/sandboxes/`).
- **Complexity-Aware Neural Routing:** Dynamically routes heavy architectural modules to high-tier models and lightweight utilities to fast local LLMs (LM Studio, Ollama, DeepSeek, OpenAI, Anthropic Claude).
- **Built-in Language Server Protocol (`abx lsp`):** Real-time error underlines and hover docs in VS Code, Cursor, and Neovim.
- **Built-in Terminal Manual (`abx docs`):** Exhaustive documentation viewer accessible directly from CLI.
- **Single Portable Binary:** Available as standalone `Abstralix.exe` with hybrid plugin discovery.

---

## Quick Start

### Option A: Standalone Executable (Windows)
Download `Abstralix.exe` from [Releases](https://github.com/lithcoreit/abstralix/releases), put it in any folder or add to `PATH`:
```powershell
Abstralix.exe --help
Abstralix.exe docs user
```

### Option B: From Source (Python 3.11+)
```powershell
git clone https://github.com/lithcoreit/abstralix.git
cd abstralix
python -m venv venv
.\venv\Scripts\activate   # Linux/macOS: source venv/bin/activate
pip install -e .
```

Verify your setup:
```powershell
abx doctor
```

---

## Toolchain Workflow

### 1. Initialize a Project
```powershell
abx init my_service
```
This scaffolds an annotated `my_service.abx` architecture and `abx.config.json`.

### 2. Static Analysis (Zero Tokens / Zero Cost)
Instantly validates syntax, hierarchy, scope, DAG cycles, and provider coverage without making LLM calls:
```powershell
abx check my_service.abx
```

### 3. Inspect Graph Topology & Complexity
Visualize the dependency hierarchy and normalized complexity scores (`0.0` to `1.0`):
```powershell
abx inspect my_service.abx
```

### 4. Concurrent Compilation & Verification
Orchestrates isolated LLMs, executes sandboxed invariant tests, and exports clean production code:
```powershell
abx build my_service.abx --clean
```

---

## Specification Example (`.abx`)

An end-to-end multi-file service with dependencies, libraries, and automated testing:

```abstralix
folder auth_service {
    @lang = "python"
    @lib = ["hashlib"]
    @max_try = 3
    @max_session = 2

    folder core {
        file security.py {
            @info = "Cryptographic utilities"

            void clean_salt {
                @info = "Strips whitespace and converts salt to lowercase"
                @in = { raw_salt = "str" }
                @out = { clean_salt = "str" }
                @context = "Strip leading/trailing whitespace and return lowercase string."
                @invariant = "if input(raw_salt=' ABC ') != 'abc': incomplete('Failed')\ncomplete()"
            }
        }

        file hasher.py {
            @import = ["/auth_service/core/security.py"]

            void hash_password {
                @use = ["clean_salt"]
                @info = "Hashes password with cleaned salt using SHA-256"
                @in = { password = "str", salt = "str" }
                @out = { digest = "str" }
                @context = "First clean salt using clean_salt(salt), then return hashlib.sha256((password + clean_salt).encode()).hexdigest()."
                @checkpoint = true
                @invariant = auto
            }
        }
    }
}
```

---

## Configuration (`abx.config.json`)

Configure local GPU servers (LM Studio, Ollama) and cloud providers by priority and complexity range:

```json
{
  "settings": {
    "dev_mode": false,
    "default_output": "./build"
  },
  "defaults": {
    "@max_try": 3,
    "@max_session": 2,
    "@judges": 0,
    "@rollback_depth": 2
  },
  "providers": [
    {
      "name": "local_gpu",
      "adapter": "openai_compatible",
      "base_url": "http://localhost:1234/v1",
      "api_key": "not-needed",
      "model": "qwen2.5-coder-7b",
      "roles": ["code_generation", "test_generation"],
      "min_complexity": 0.0,
      "max_complexity": 0.5,
      "priority": 1,
      "max_concurrency": 1
    },
    {
      "name": "cloud_heavy",
      "adapter": "anthropic",
      "base_url": "default",
      "api_key": "env:ANTHROPIC_API_KEY",
      "model": "claude-3-5-sonnet-20241022",
      "roles": ["code_generation", "judging"],
      "min_complexity": 0.45,
      "max_complexity": 1.0,
      "priority": 2,
      "max_concurrency": 4
    }
  ]
}
```

---

## Roadmap & Next Milestones

- [ ] **Internal Worker Model Fine-Tuning:** Training open-weights models specifically for atomic void code generation, invariant testing, and one-shot self-correction.
- [ ] **Architect Model Fine-Tuning:** Training dedicated planner models to transform high-level human requirements into deep, multi-file `.abx` architectural specifications.
- [ ] **Direct Modern IDE Integration:** Official extensions for VS Code, Cursor, and JetBrains powered by the built-in `abx lsp` Language Server Protocol daemon.
- [ ] **Markup & Domain-Specific Language Support:** Expanding language adapters to include HTML, CSS, SQL, Dockerfile, YAML, and configuration specifications.

---

## Author & Contact

- **Author:** **LITH::core**
- **Email:** [lithcoreit@gmail.com](mailto:lithcoreit@gmail.com)
- **Repository:** [https://github.com/lithcoreit/abstralix](https://github.com/lithcoreit/abstralix)

For collaboration, inquiries, or bug reports, contact via email or open an issue on GitHub.

---

## License

This project is licensed under the **MIT License** -- see the [LICENSE](LICENSE) file for details.