# Code Architecture Knowledge Graph — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a system that parses Python + TypeScript codebases into a typed property graph and renders an interactive 3D visualization with stacked abstraction layers and force-directed layouts.

**Architecture:** Python CLI uses tree-sitter to parse ASTs, extracts nodes/edges, writes JSON to `.callgraph/`. A Three.js web app reads the JSON and renders an interactive 3D scene with stacked layers, 3D blocks, and bezier curve edges.

**Tech Stack:** Python 3.12+, tree-sitter, Three.js, tween.js, d3-force-3d, vanilla JS (ES modules)

---

## Task 1: Project scaffolding and Python environment

**Files:**
- Create: `pyproject.toml`
- Create: `src/callgraph/__init__.py`
- Create: `src/callgraph/cli.py`
- Create: `tests/__init__.py`
- Create: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "callgraph"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "tree-sitter>=0.23",
    "tree-sitter-python>=0.23",
    "tree-sitter-typescript>=0.23",
    "tree-sitter-javascript>=0.23",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov"]

[project.scripts]
callgraph = "callgraph.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 2: Create src/callgraph/__init__.py and src/callgraph/cli.py**

```python
# src/callgraph/cli.py
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Build code architecture graph")
    parser.add_argument("path", help="Path to the repository to analyze")
    parser.add_argument("-o", "--output", default=".callgraph", help="Output directory")
    args = parser.parse_args()
    print(f"Analyzing {args.path}...")

if __name__ == "__main__":
    main()
```

**Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
.callgraph/
node_modules/
```

**Step 4: Create virtual environment and install**

Run: `cd /home/hendrik/coding/call-graph-v2 && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`

**Step 5: Verify CLI runs**

Run: `source .venv/bin/activate && callgraph test-project/`
Expected: `Analyzing test-project/...`

**Step 6: Commit**

```bash
git add pyproject.toml src/ tests/ .gitignore
git commit -m "feat: scaffold Python project with CLI entry point"
```

---

## Task 2: File discovery and language detection

**Files:**
- Create: `src/callgraph/discovery.py`
- Create: `tests/test_discovery.py`

**Step 1: Write the failing test**

```python
# tests/test_discovery.py
from pathlib import Path
from callgraph.discovery import discover_files

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_discovers_python_files():
    files = discover_files(TEST_PROJECT)
    py_files = [f for f in files if f["language"] == "python"]
    assert len(py_files) == 16
    paths = {f["path"] for f in py_files}
    assert "backend/services/auth_service.py" in paths

def test_discovers_typescript_files():
    files = discover_files(TEST_PROJECT)
    ts_files = [f for f in files if f["language"] in ("typescript", "typescriptreact")]
    assert len(ts_files) >= 10
    paths = {f["path"] for f in ts_files}
    assert "frontend/src/App.tsx" in paths

def test_skips_non_source_files():
    files = discover_files(TEST_PROJECT)
    extensions = {Path(f["path"]).suffix for f in files}
    assert ".md" not in extensions
    assert ".json" not in extensions
    assert ".toml" not in extensions
    assert ".html" not in extensions

def test_file_entry_has_required_fields():
    files = discover_files(TEST_PROJECT)
    for f in files:
        assert "path" in f
        assert "absolute_path" in f
        assert "language" in f
```

**Step 2: Run test to verify it fails**

Run: `cd /home/hendrik/coding/call-graph-v2 && source .venv/bin/activate && pytest tests/test_discovery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'callgraph.discovery'`

**Step 3: Implement discovery.py**

```python
# src/callgraph/discovery.py
from pathlib import Path

EXTENSION_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
}

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "dist", ".callgraph"}

def discover_files(root: Path) -> list[dict]:
    root = Path(root).resolve()
    files = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in EXTENSION_MAP:
            rel = str(path.relative_to(root))
            files.append({
                "path": rel,
                "absolute_path": str(path),
                "language": EXTENSION_MAP[path.suffix],
            })
    return sorted(files, key=lambda f: f["path"])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_discovery.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/callgraph/discovery.py tests/test_discovery.py
git commit -m "feat: file discovery with language detection"
```

---

## Task 3: Python AST parsing — node extraction

**Files:**
- Create: `src/callgraph/parsers/__init__.py`
- Create: `src/callgraph/parsers/python_parser.py`
- Create: `tests/test_python_parser.py`

**Step 1: Write the failing test**

```python
# tests/test_python_parser.py
from pathlib import Path
from callgraph.parsers.python_parser import parse_python_file

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_extracts_classes():
    result = parse_python_file(
        TEST_PROJECT / "backend/models/user.py",
        "backend/models/user.py"
    )
    classes = [n for n in result["nodes"] if n["type"] == "class"]
    names = {c["name"] for c in classes}
    assert "Base" in names
    assert "User" in names

def test_extracts_functions():
    result = parse_python_file(
        TEST_PROJECT / "backend/services/auth_service.py",
        "backend/services/auth_service.py"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert "hash_password" in names
    assert "verify_password" in names
    assert "create_access_token" in names
    assert "decode_token" in names
    assert "authenticate_user" in names
    assert "register_user" in names

def test_extracts_imports():
    result = parse_python_file(
        TEST_PROJECT / "backend/services/task_service.py",
        "backend/services/task_service.py"
    )
    imports = result["imports"]
    imported_modules = {imp["module"] for imp in imports}
    assert any("backend.models.task" in m for m in imported_modules)
    assert any("backend.services.notification_service" in m for m in imported_modules)

def test_extracts_methods_inside_class():
    result = parse_python_file(
        TEST_PROJECT / "backend/models/user.py",
        "backend/models/user.py"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert "__repr__" in names

def test_node_has_line_count():
    result = parse_python_file(
        TEST_PROJECT / "backend/services/auth_service.py",
        "backend/services/auth_service.py"
    )
    for node in result["nodes"]:
        assert "lines_of_code" in node
        assert node["lines_of_code"] > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_python_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement python_parser.py**

```python
# src/callgraph/parsers/__init__.py
```

```python
# src/callgraph/parsers/python_parser.py
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())

def parse_python_file(file_path, relative_path: str) -> dict:
    parser = Parser(PY_LANGUAGE)
    source = open(file_path, "rb").read()
    tree = parser.parse(source)

    nodes = []
    imports = []

    _extract_nodes(tree.root_node, relative_path, source, nodes)
    _extract_imports(tree.root_node, source, imports)

    total_lines = source.count(b"\n") + 1

    return {
        "file_path": relative_path,
        "language": "python",
        "lines_of_code": total_lines,
        "nodes": nodes,
        "imports": imports,
    }

def _extract_nodes(node, file_path: str, source: bytes, result: list):
    if node.type == "class_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source[name_node.start_byte:name_node.end_byte].decode()
            loc = node.end_point[0] - node.start_point[0] + 1
            result.append({
                "id": f"class:{file_path}:{name}",
                "type": "class",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
            })

    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source[name_node.start_byte:name_node.end_byte].decode()
            loc = node.end_point[0] - node.start_point[0] + 1
            result.append({
                "id": f"func:{file_path}:{name}",
                "type": "function",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
            })

    for child in node.children:
        _extract_nodes(child, file_path, source, result)

def _extract_imports(node, source: bytes, result: list):
    if node.type == "import_from_statement":
        module_node = node.child_by_field_name("module_name")
        if module_node:
            module = source[module_node.start_byte:module_node.end_byte].decode()
            names = []
            for child in node.children:
                if child.type == "dotted_name" and child != module_node:
                    names.append(source[child.start_byte:child.end_byte].decode())
                elif child.type == "aliased_import":
                    name_child = child.child_by_field_name("name")
                    if name_child:
                        names.append(source[name_child.start_byte:name_child.end_byte].decode())
            result.append({"module": module, "names": names})

    elif node.type == "import_statement":
        for child in node.children:
            if child.type == "dotted_name":
                module = source[child.start_byte:child.end_byte].decode()
                result.append({"module": module, "names": []})

    for child in node.children:
        if node.type not in ("import_from_statement", "import_statement"):
            _extract_imports(child, source, result)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_python_parser.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/callgraph/parsers/ tests/test_python_parser.py
git commit -m "feat: Python AST parser extracting classes, functions, imports"
```

---

## Task 4: TypeScript/JS AST parsing — node extraction

**Files:**
- Create: `src/callgraph/parsers/typescript_parser.py`
- Create: `tests/test_typescript_parser.py`

**Step 1: Write the failing test**

```python
# tests/test_typescript_parser.py
from pathlib import Path
from callgraph.parsers.typescript_parser import parse_typescript_file

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_extracts_functions_from_tsx():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/App.tsx",
        "frontend/src/App.tsx"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert "App" in names or "ProtectedRoute" in names

def test_extracts_functions_from_ts():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/services/auth.ts",
        "frontend/src/services/auth.ts"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert "login" in names
    assert "register" in names
    assert "logout" in names
    assert "getToken" in names

def test_extracts_interfaces():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/types/api.ts",
        "frontend/src/types/api.ts"
    )
    interfaces = [n for n in result["nodes"] if n["type"] == "class"]
    names = {i["name"] for i in interfaces}
    assert "Task" in names
    assert "User" in names
    assert "LoginRequest" in names

def test_extracts_imports():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/components/TaskList.tsx",
        "frontend/src/components/TaskList.tsx"
    )
    imports = result["imports"]
    sources = {imp["module"] for imp in imports}
    assert any("useTasks" in s for s in sources)
    assert any("TaskCard" in s for s in sources)

def test_node_has_line_count():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/hooks/useTasks.ts",
        "frontend/src/hooks/useTasks.ts"
    )
    for node in result["nodes"]:
        assert "lines_of_code" in node
        assert node["lines_of_code"] > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_typescript_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement typescript_parser.py**

```python
# src/callgraph/parsers/typescript_parser.py
import tree_sitter_typescript as tstypescript
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser

TSX_LANGUAGE = Language(tstypescript.language_tsx())
TS_LANGUAGE = Language(tstypescript.language_typescript())
JS_LANGUAGE = Language(tsjavascript.language())

LANGUAGE_MAP = {
    "typescript": TS_LANGUAGE,
    "typescriptreact": TSX_LANGUAGE,
    "javascript": JS_LANGUAGE,
    "javascriptreact": JS_LANGUAGE,  # tree-sitter JS handles JSX
}

def parse_typescript_file(file_path, relative_path: str, language: str = None) -> dict:
    if language is None:
        if str(file_path).endswith(".tsx"):
            language = "typescriptreact"
        elif str(file_path).endswith(".ts"):
            language = "typescript"
        elif str(file_path).endswith(".jsx"):
            language = "javascriptreact"
        else:
            language = "javascript"

    lang = LANGUAGE_MAP[language]
    parser = Parser(lang)
    source = open(file_path, "rb").read()
    tree = parser.parse(source)

    nodes = []
    imports = []

    _extract_nodes(tree.root_node, relative_path, source, nodes)
    _extract_imports(tree.root_node, source, imports)

    total_lines = source.count(b"\n") + 1

    return {
        "file_path": relative_path,
        "language": language,
        "lines_of_code": total_lines,
        "nodes": nodes,
        "imports": imports,
    }

def _extract_nodes(node, file_path: str, source: bytes, result: list):
    # Function declarations: function foo() {}
    if node.type == "function_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            _add_function_node(name_node, node, file_path, source, result)

    # Arrow functions assigned to const: const foo = () => {}
    if node.type == "lexical_declaration":
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if name_node and value_node and value_node.type == "arrow_function":
                    _add_function_node(name_node, node, file_path, source, result)

    # Export default function: export default function App() {}
    if node.type == "export_statement":
        for child in node.children:
            if child.type == "function_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    _add_function_node(name_node, child, file_path, source, result)
            if child.type == "lexical_declaration":
                for sub in child.children:
                    if sub.type == "variable_declarator":
                        name_node = sub.child_by_field_name("name")
                        value_node = sub.child_by_field_name("value")
                        if name_node and value_node and value_node.type == "arrow_function":
                            _add_function_node(name_node, child, file_path, source, result)

    # Interfaces and type aliases
    if node.type in ("interface_declaration", "type_alias_declaration"):
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source[name_node.start_byte:name_node.end_byte].decode()
            loc = node.end_point[0] - node.start_point[0] + 1
            result.append({
                "id": f"class:{file_path}:{name}",
                "type": "class",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
            })

    # Class declarations
    if node.type == "class_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source[name_node.start_byte:name_node.end_byte].decode()
            loc = node.end_point[0] - node.start_point[0] + 1
            result.append({
                "id": f"class:{file_path}:{name}",
                "type": "class",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
            })

    for child in node.children:
        # Don't recurse into function bodies for top-level extraction
        if node.type not in ("function_declaration", "arrow_function", "method_definition"):
            _extract_nodes(child, file_path, source, result)

def _add_function_node(name_node, scope_node, file_path, source, result):
    name = source[name_node.start_byte:name_node.end_byte].decode()
    loc = scope_node.end_point[0] - scope_node.start_point[0] + 1
    result.append({
        "id": f"func:{file_path}:{name}",
        "type": "function",
        "name": name,
        "file_path": file_path,
        "lines_of_code": loc,
        "start_line": scope_node.start_point[0] + 1,
        "end_line": scope_node.end_point[0] + 1,
    })

def _extract_imports(node, source: bytes, result: list):
    if node.type == "import_statement":
        source_node = node.child_by_field_name("source")
        if source_node:
            module = source[source_node.start_byte:source_node.end_byte].decode().strip("'\"")
            names = []
            for child in node.children:
                if child.type == "import_clause":
                    for sub in child.children:
                        if sub.type == "identifier":
                            names.append(source[sub.start_byte:sub.end_byte].decode())
                        elif sub.type == "named_imports":
                            for spec in sub.children:
                                if spec.type == "import_specifier":
                                    name_node = spec.child_by_field_name("name")
                                    if name_node:
                                        names.append(source[name_node.start_byte:name_node.end_byte].decode())
            result.append({"module": module, "names": names})

    for child in node.children:
        if node.type != "import_statement":
            _extract_imports(child, source, result)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_typescript_parser.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/callgraph/parsers/typescript_parser.py tests/test_typescript_parser.py
git commit -m "feat: TypeScript/JS AST parser extracting functions, interfaces, imports"
```

---

## Task 5: Graph builder — assemble nodes and edges

**Files:**
- Create: `src/callgraph/graph_builder.py`
- Create: `tests/test_graph_builder.py`

**Step 1: Write the failing test**

```python
# tests/test_graph_builder.py
from pathlib import Path
from callgraph.graph_builder import build_graph

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_builds_directory_nodes():
    graph = build_graph(TEST_PROJECT)
    dir_nodes = [n for n in graph["nodes"] if n["type"] == "directory"]
    names = {n["name"] for n in dir_nodes}
    assert "backend" in names
    assert "services" in names
    assert "components" in names

def test_builds_file_nodes():
    graph = build_graph(TEST_PROJECT)
    file_nodes = [n for n in graph["nodes"] if n["type"] == "file"]
    names = {n["name"] for n in file_nodes}
    assert "auth_service.py" in names
    assert "App.tsx" in names

def test_builds_function_nodes():
    graph = build_graph(TEST_PROJECT)
    func_nodes = [n for n in graph["nodes"] if n["type"] == "function"]
    names = {n["name"] for n in func_nodes}
    assert "authenticate_user" in names
    assert "login" in names

def test_builds_contains_edges():
    graph = build_graph(TEST_PROJECT)
    contains = [e for e in graph["edges"] if e["type"] == "contains"]
    assert len(contains) > 0
    # Directory contains file
    pairs = {(e["from"], e["to"]) for e in contains}
    assert any("dir:backend/services" in f and "file:backend/services/auth_service.py" in t for f, t in pairs)

def test_builds_imports_edges():
    graph = build_graph(TEST_PROJECT)
    imports = [e for e in graph["edges"] if e["type"] == "imports"]
    assert len(imports) > 0

def test_assigns_abstraction_level():
    graph = build_graph(TEST_PROJECT)
    file_nodes = {n["id"]: n for n in graph["nodes"] if n["type"] == "file"}
    # models should be level 0
    model_node = file_nodes.get("file:backend/models/user.py")
    if model_node:
        assert model_node["abstraction_level"] == 0
    # services should be level 1
    svc_node = file_nodes.get("file:backend/services/auth_service.py")
    if svc_node:
        assert svc_node["abstraction_level"] == 1

def test_nodes_have_language():
    graph = build_graph(TEST_PROJECT)
    file_nodes = [n for n in graph["nodes"] if n["type"] == "file"]
    for n in file_nodes:
        assert "language" in n
        assert n["language"] in ("python", "typescript", "typescriptreact", "javascript", "javascriptreact")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_builder.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement graph_builder.py**

```python
# src/callgraph/graph_builder.py
from pathlib import Path
from callgraph.discovery import discover_files
from callgraph.parsers.python_parser import parse_python_file
from callgraph.parsers.typescript_parser import parse_typescript_file

ABSTRACTION_LEVELS = {
    "models": 0, "types": 0, "schemas": 0,
    "services": 1, "utils": 1, "hooks": 1, "lib": 1,
    "api": 2, "routes": 2, "components": 2, "views": 2,
    "main": 3, "app": 3, "index": 3,
}

PYTHON_LANGUAGES = {"python"}
TS_LANGUAGES = {"typescript", "typescriptreact", "javascript", "javascriptreact"}

def build_graph(root: Path) -> dict:
    root = Path(root).resolve()
    files = discover_files(root)

    nodes = []
    edges = []
    seen_dirs = set()
    file_parse_results = {}

    # Build directory nodes and contains edges
    for f in files:
        parts = Path(f["path"]).parts
        for i in range(len(parts) - 1):
            dir_path = str(Path(*parts[:i+1]))
            if dir_path not in seen_dirs:
                seen_dirs.add(dir_path)
                dir_name = parts[i]
                nodes.append({
                    "id": f"dir:{dir_path}",
                    "type": "directory",
                    "name": dir_name,
                    "file_path": dir_path,
                    "language": None,
                    "lines_of_code": 0,
                    "abstraction_level": _get_abstraction_level(dir_path),
                    "parent": f"dir:{str(Path(*parts[:i]))}" if i > 0 else None,
                })
                # Directory containment
                if i > 0:
                    parent_path = str(Path(*parts[:i]))
                    edges.append({
                        "from": f"dir:{parent_path}",
                        "to": f"dir:{dir_path}",
                        "type": "contains",
                        "weight": 1,
                    })

    # Parse files and build file/function/class nodes
    for f in files:
        rel_path = f["path"]
        abs_path = f["absolute_path"]
        lang = f["language"]

        # Parse AST
        if lang in PYTHON_LANGUAGES:
            parse_result = parse_python_file(abs_path, rel_path)
        elif lang in TS_LANGUAGES:
            parse_result = parse_typescript_file(abs_path, rel_path, lang)
        else:
            continue

        file_parse_results[rel_path] = parse_result

        # File node
        file_id = f"file:{rel_path}"
        parent_dir = str(Path(rel_path).parent)
        abstraction = _get_abstraction_level(rel_path)

        nodes.append({
            "id": file_id,
            "type": "file",
            "name": Path(rel_path).name,
            "file_path": rel_path,
            "language": lang,
            "lines_of_code": parse_result["lines_of_code"],
            "abstraction_level": abstraction,
            "export_count": len(parse_result["nodes"]),
            "parent": f"dir:{parent_dir}",
        })

        # Dir -> file contains edge
        edges.append({
            "from": f"dir:{parent_dir}",
            "to": file_id,
            "type": "contains",
            "weight": 1,
        })

        # Function/class nodes
        for sub_node in parse_result["nodes"]:
            sub_node["language"] = lang
            sub_node["abstraction_level"] = abstraction
            sub_node["parent"] = file_id
            nodes.append(sub_node)
            edges.append({
                "from": file_id,
                "to": sub_node["id"],
                "type": "contains",
                "weight": 1,
            })

    # Build import edges (file-level)
    _build_import_edges(file_parse_results, files, edges)

    return {"nodes": nodes, "edges": edges}

def _get_abstraction_level(path: str) -> int:
    parts = Path(path).parts
    for part in parts:
        stem = part.replace(".py", "").replace(".ts", "").replace(".tsx", "").replace(".js", "")
        if stem in ABSTRACTION_LEVELS:
            return ABSTRACTION_LEVELS[stem]
    return 1  # default to middle

def _build_import_edges(parse_results: dict, files: list, edges: list):
    file_paths = {f["path"] for f in files}

    for source_path, result in parse_results.items():
        source_id = f"file:{source_path}"
        for imp in result["imports"]:
            module = imp["module"]
            target = _resolve_import(module, source_path, file_paths)
            if target:
                target_id = f"file:{target}"
                edges.append({
                    "from": source_id,
                    "to": target_id,
                    "type": "imports",
                    "weight": len(imp.get("names", [])) or 1,
                })

def _resolve_import(module: str, source_path: str, file_paths: set) -> str | None:
    # Handle relative imports (./foo, ../foo)
    if module.startswith("."):
        source_dir = str(Path(source_path).parent)
        if module.startswith(".."):
            source_dir = str(Path(source_dir).parent)
            module = module[2:].lstrip("/")
        else:
            module = module[1:].lstrip("/")

        candidates = [
            f"{source_dir}/{module}.ts",
            f"{source_dir}/{module}.tsx",
            f"{source_dir}/{module}.js",
            f"{source_dir}/{module}/index.ts",
            f"{source_dir}/{module}/index.tsx",
        ]
        for c in candidates:
            normalized = str(Path(c))
            if normalized in file_paths:
                return normalized
        return None

    # Handle Python-style dotted imports (backend.services.auth_service)
    path_from_dots = module.replace(".", "/")
    candidates = [
        f"{path_from_dots}.py",
        f"{path_from_dots}/__init__.py",
        f"{path_from_dots}.ts",
        f"{path_from_dots}.tsx",
    ]
    for c in candidates:
        if c in file_paths:
            return c
    return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_builder.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/callgraph/graph_builder.py tests/test_graph_builder.py
git commit -m "feat: graph builder assembling nodes, edges, and abstraction levels"
```

---

## Task 6: JSON output and CLI integration

**Files:**
- Create: `src/callgraph/output.py`
- Modify: `src/callgraph/cli.py`
- Create: `tests/test_output.py`

**Step 1: Write the failing test**

```python
# tests/test_output.py
import json
import tempfile
from pathlib import Path
from callgraph.output import write_graph
from callgraph.graph_builder import build_graph

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_writes_nodes_json():
    graph = build_graph(TEST_PROJECT)
    with tempfile.TemporaryDirectory() as tmpdir:
        write_graph(graph, tmpdir)
        nodes_file = Path(tmpdir) / "nodes.json"
        assert nodes_file.exists()
        nodes = json.loads(nodes_file.read_text())
        assert isinstance(nodes, list)
        assert len(nodes) > 0
        assert all("id" in n for n in nodes)

def test_writes_edges_json():
    graph = build_graph(TEST_PROJECT)
    with tempfile.TemporaryDirectory() as tmpdir:
        write_graph(graph, tmpdir)
        edges_file = Path(tmpdir) / "edges.json"
        assert edges_file.exists()
        edges = json.loads(edges_file.read_text())
        assert isinstance(edges, list)
        assert len(edges) > 0
        assert all("from" in e and "to" in e for e in edges)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_output.py -v`
Expected: FAIL

**Step 3: Implement output.py and update cli.py**

```python
# src/callgraph/output.py
import json
from pathlib import Path

def write_graph(graph: dict, output_dir: str):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "nodes.json").write_text(json.dumps(graph["nodes"], indent=2))
    (out / "edges.json").write_text(json.dumps(graph["edges"], indent=2))
```

```python
# src/callgraph/cli.py
import argparse
from pathlib import Path
from callgraph.graph_builder import build_graph
from callgraph.output import write_graph

def main():
    parser = argparse.ArgumentParser(description="Build code architecture graph")
    parser.add_argument("path", help="Path to the repository to analyze")
    parser.add_argument("-o", "--output", default=".callgraph", help="Output directory")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    print(f"Analyzing {root}...")

    graph = build_graph(root)
    write_graph(graph, args.output)

    print(f"Graph written to {args.output}/")
    print(f"  {len(graph['nodes'])} nodes")
    print(f"  {len(graph['edges'])} edges")

if __name__ == "__main__":
    main()
```

**Step 4: Run tests and verify CLI**

Run: `pytest tests/test_output.py -v`
Expected: All PASS

Run: `source .venv/bin/activate && callgraph test-project/ -o .callgraph`
Expected: Summary printed with node/edge counts

**Step 5: Commit**

```bash
git add src/callgraph/output.py src/callgraph/cli.py tests/test_output.py
git commit -m "feat: JSON output and CLI integration"
```

---

## Task 7: Three.js scaffolding — scene, camera, controls

**Files:**
- Create: `web/index.html`
- Create: `web/js/main.js`
- Create: `web/js/scene.js`

**Step 1: Create web/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Code Architecture Graph</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { overflow: hidden; background: #0a0a0f; color: #e0e0e0; font-family: monospace; }
        canvas { display: block; }
        #info-panel {
            position: fixed;
            top: 16px;
            right: 16px;
            background: rgba(20, 20, 30, 0.9);
            border: 1px solid rgba(100, 100, 140, 0.3);
            border-radius: 8px;
            padding: 16px;
            min-width: 220px;
            display: none;
            font-size: 13px;
        }
        #info-panel h3 { margin-bottom: 8px; color: #8888cc; }
        #info-panel .field { margin: 4px 0; }
        #info-panel .label { color: #888; }
        #controls {
            position: fixed;
            bottom: 16px;
            left: 16px;
            display: flex;
            gap: 8px;
        }
        #controls button {
            background: rgba(20, 20, 30, 0.9);
            border: 1px solid rgba(100, 100, 140, 0.3);
            border-radius: 4px;
            color: #e0e0e0;
            padding: 8px 16px;
            cursor: pointer;
            font-family: monospace;
        }
        #controls button:hover { background: rgba(40, 40, 60, 0.9); }
    </style>
</head>
<body>
    <div id="info-panel">
        <h3 id="info-name"></h3>
        <div class="field"><span class="label">Type: </span><span id="info-type"></span></div>
        <div class="field"><span class="label">LOC: </span><span id="info-loc"></span></div>
        <div class="field"><span class="label">Language: </span><span id="info-lang"></span></div>
        <div class="field"><span class="label">Path: </span><span id="info-path"></span></div>
    </div>
    <div id="controls">
        <button id="btn-reset">Reset View</button>
    </div>
    <script type="importmap">
    {
        "imports": {
            "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
            "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/",
            "@tweenjs/tween.js": "https://cdn.jsdelivr.net/npm/@tweenjs/tween.js@25/dist/tween.esm.js"
        }
    }
    </script>
    <script type="module" src="js/main.js"></script>
</body>
</html>
```

**Step 2: Create web/js/scene.js**

```javascript
// web/js/scene.js
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import * as TWEEN from '@tweenjs/tween.js';

export function createScene() {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0f);
    scene.fog = new THREE.FogExp2(0x0a0a0f, 0.008);

    const camera = new THREE.PerspectiveCamera(
        60, window.innerWidth / window.innerHeight, 0.1, 1000
    );
    camera.position.set(30, 40, 30);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    document.body.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 5;
    controls.maxDistance = 200;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x404060, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(20, 40, 20);
    scene.add(directionalLight);

    // Grid helper for ground reference
    const grid = new THREE.GridHelper(100, 50, 0x222244, 0x111122);
    grid.position.y = -1;
    scene.add(grid);

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    return { scene, camera, renderer, controls };
}

export function animate(renderer, scene, camera, controls) {
    function loop() {
        requestAnimationFrame(loop);
        controls.update();
        TWEEN.update();
        renderer.render(scene, camera);
    }
    loop();
}

export function animateCamera(camera, controls, targetPos, targetLookAt, duration = 1000) {
    const startPos = camera.position.clone();
    const startTarget = controls.target.clone();

    new TWEEN.Tween({ t: 0 })
        .to({ t: 1 }, duration)
        .easing(TWEEN.Easing.Cubic.InOut)
        .onUpdate(({ t }) => {
            camera.position.lerpVectors(startPos, targetPos, t);
            controls.target.lerpVectors(startTarget, targetLookAt, t);
        })
        .start();
}
```

**Step 3: Create web/js/main.js**

```javascript
// web/js/main.js
import * as THREE from 'three';
import { createScene, animate, animateCamera } from './scene.js';

const { scene, camera, renderer, controls } = createScene();

// Default camera position for reset
const defaultCameraPos = new THREE.Vector3(30, 40, 30);
const defaultTarget = new THREE.Vector3(0, 0, 0);

document.getElementById('btn-reset').addEventListener('click', () => {
    animateCamera(camera, controls, defaultCameraPos, defaultTarget);
});

animate(renderer, scene, camera, controls);

console.log('Scene initialized');
```

**Step 4: Test in browser**

Run: `cd /home/hendrik/coding/call-graph-v2 && python3 -m http.server 8080 --directory web`

Open `http://localhost:8080` — should see dark scene with grid and orbit controls working.

**Step 5: Commit**

```bash
git add web/
git commit -m "feat: Three.js scene with camera, controls, and lighting"
```

---

## Task 8: Load graph data and render layers

**Files:**
- Create: `web/js/graph-loader.js`
- Create: `web/js/layers.js`
- Modify: `web/js/main.js`

**Step 1: Create web/js/graph-loader.js**

```javascript
// web/js/graph-loader.js
export async function loadGraph(basePath = '..') {
    const [nodesRes, edgesRes] = await Promise.all([
        fetch(`${basePath}/.callgraph/nodes.json`),
        fetch(`${basePath}/.callgraph/edges.json`),
    ]);
    const nodes = await nodesRes.json();
    const edges = await edgesRes.json();
    return { nodes, edges };
}

export function groupByAbstractionLevel(nodes) {
    const layers = {};
    for (const node of nodes) {
        if (node.type !== 'file') continue;
        const level = node.abstraction_level ?? 1;
        if (!layers[level]) layers[level] = [];
        layers[level].push(node);
    }
    return layers;
}
```

**Step 2: Create web/js/layers.js**

```javascript
// web/js/layers.js
import * as THREE from 'three';

const LAYER_COLORS = {
    0: 0x4466aa, // models — blue
    1: 0x44aa66, // services — green
    2: 0xaa6644, // api/components — orange
    3: 0xaa44aa, // entry points — purple
};

const LANGUAGE_COLORS = {
    python: 0x3572A5,
    typescript: 0x3178C6,
    typescriptreact: 0x3178C6,
    javascript: 0xF7DF1E,
    javascriptreact: 0xF7DF1E,
};

const LAYER_LABELS = {
    0: 'models / types',
    1: 'services / hooks',
    2: 'api / components',
    3: 'entry points',
};

const LAYER_SPACING = 12;
const BLOCK_BASE = 1.5;
const LOC_SCALE = 0.06;
const LAYER_SIZE = 40;

export function createLayers(layerGroups, scene) {
    const layerMeshes = {};
    const nodeMeshes = {};
    const nodeDataMap = new Map();

    const levels = Object.keys(layerGroups).map(Number).sort();

    for (const level of levels) {
        const y = level * LAYER_SPACING;
        const nodes = layerGroups[level];

        // Layer plane
        const planeGeo = new THREE.BoxGeometry(LAYER_SIZE, 0.2, LAYER_SIZE);
        const planeMat = new THREE.MeshPhongMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.15,
        });
        const plane = new THREE.Mesh(planeGeo, planeMat);
        plane.position.y = y;
        plane.userData = { type: 'layer', level };
        scene.add(plane);
        layerMeshes[level] = plane;

        // Layer label
        const label = createTextSprite(LAYER_LABELS[level] || `level ${level}`, LAYER_COLORS[level] || 0x666666);
        label.position.set(-LAYER_SIZE / 2 - 3, y + 1, 0);
        scene.add(label);

        // Node blocks — simple grid layout for now, force-directed in Task 9
        const cols = Math.ceil(Math.sqrt(nodes.length));
        const spacing = LAYER_SIZE / (cols + 1);

        nodes.forEach((node, i) => {
            const col = i % cols;
            const row = Math.floor(i / cols);
            const x = (col - cols / 2) * spacing + spacing / 2;
            const z = (row - cols / 2) * spacing + spacing / 2;
            const height = Math.max(1, node.lines_of_code * LOC_SCALE);

            const geo = new THREE.BoxGeometry(BLOCK_BASE, height, BLOCK_BASE);
            const color = LANGUAGE_COLORS[node.language] || 0x888888;
            const mat = new THREE.MeshPhongMaterial({ color });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(x, y + height / 2 + 0.1, z);
            mesh.userData = { type: 'node', nodeData: node };
            scene.add(mesh);

            nodeMeshes[node.id] = mesh;
            nodeDataMap.set(mesh, node);
        });
    }

    return { layerMeshes, nodeMeshes, nodeDataMap };
}

function createTextSprite(text, color = 0xffffff) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.font = '28px monospace';
    ctx.fillStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.fillText(text, 10, 40);

    const texture = new THREE.CanvasTexture(canvas);
    const mat = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(16, 2, 1);
    return sprite;
}
```

**Step 3: Update web/js/main.js**

```javascript
// web/js/main.js
import * as THREE from 'three';
import { createScene, animate, animateCamera } from './scene.js';
import { loadGraph, groupByAbstractionLevel } from './graph-loader.js';
import { createLayers } from './layers.js';

const { scene, camera, renderer, controls } = createScene();

const defaultCameraPos = new THREE.Vector3(30, 40, 30);
const defaultTarget = new THREE.Vector3(0, 10, 0);

camera.position.copy(defaultCameraPos);
controls.target.copy(defaultTarget);

document.getElementById('btn-reset').addEventListener('click', () => {
    animateCamera(camera, controls, defaultCameraPos, defaultTarget);
});

async function init() {
    try {
        const graph = await loadGraph('..');
        const layerGroups = groupByAbstractionLevel(graph.nodes);
        const { layerMeshes, nodeMeshes, nodeDataMap } = createLayers(layerGroups, scene);
        console.log(`Loaded ${graph.nodes.length} nodes, ${graph.edges.length} edges`);
    } catch (err) {
        console.error('Failed to load graph:', err);
    }
}

init();
animate(renderer, scene, camera, controls);
```

**Step 4: Generate graph data and test**

Run: `source .venv/bin/activate && callgraph test-project/ -o .callgraph`
Run: `python3 -m http.server 8080` (from project root)

Open `http://localhost:8080/web/` — should see stacked colored layer planes with 3D blocks.

**Step 5: Commit**

```bash
git add web/js/graph-loader.js web/js/layers.js web/js/main.js
git commit -m "feat: load graph JSON and render stacked layers with 3D blocks"
```

---

## Task 9: Force-directed layout within layers

**Files:**
- Create: `web/js/layout.js`
- Modify: `web/js/layers.js`

**Step 1: Create web/js/layout.js**

```javascript
// web/js/layout.js

// Simple force-directed layout for nodes within a layer
export function computeForceLayout(nodes, edges, iterations = 200) {
    const nodeIds = new Set(nodes.map(n => n.id));
    const relevantEdges = edges.filter(e => nodeIds.has(e.from) && nodeIds.has(e.to));

    // Initialize positions randomly in a bounded area
    const positions = {};
    const AREA = 30;
    for (const node of nodes) {
        positions[node.id] = {
            x: (Math.random() - 0.5) * AREA,
            z: (Math.random() - 0.5) * AREA,
            vx: 0,
            vz: 0,
        };
    }

    const REPULSION = 80;
    const ATTRACTION = 0.02;
    const DAMPING = 0.9;
    const CENTER_PULL = 0.01;

    for (let iter = 0; iter < iterations; iter++) {
        // Repulsion between all pairs
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const a = positions[nodes[i].id];
                const b = positions[nodes[j].id];
                let dx = a.x - b.x;
                let dz = a.z - b.z;
                let dist = Math.sqrt(dx * dx + dz * dz) + 0.01;
                let force = REPULSION / (dist * dist);
                let fx = (dx / dist) * force;
                let fz = (dz / dist) * force;
                a.vx += fx; a.vz += fz;
                b.vx -= fx; b.vz -= fz;
            }
        }

        // Attraction along edges
        for (const edge of relevantEdges) {
            const a = positions[edge.from];
            const b = positions[edge.to];
            if (!a || !b) continue;
            let dx = b.x - a.x;
            let dz = b.z - a.z;
            let dist = Math.sqrt(dx * dx + dz * dz) + 0.01;
            let force = dist * ATTRACTION;
            let fx = (dx / dist) * force;
            let fz = (dz / dist) * force;
            a.vx += fx; a.vz += fz;
            b.vx -= fx; b.vz -= fz;
        }

        // Center pull
        for (const node of nodes) {
            const p = positions[node.id];
            p.vx -= p.x * CENTER_PULL;
            p.vz -= p.z * CENTER_PULL;
        }

        // Apply velocity with damping
        for (const node of nodes) {
            const p = positions[node.id];
            p.vx *= DAMPING;
            p.vz *= DAMPING;
            p.x += p.vx;
            p.z += p.vz;
        }
    }

    return positions;
}
```

**Step 2: Update layers.js to use force layout**

Replace the simple grid layout section in `createLayers` with force-directed positions. In the `nodes.forEach` block, use positions from `computeForceLayout` instead of grid math.

Modify `web/js/layers.js` to import and use `computeForceLayout`:
- Import: `import { computeForceLayout } from './layout.js';`
- Before the node loop: `const positions = computeForceLayout(nodes, allEdges);`
- Replace grid x/z with `positions[node.id].x` and `positions[node.id].z`

The full signature change for `createLayers` becomes:

```javascript
export function createLayers(layerGroups, edges, scene) {
```

Update `main.js` to pass `graph.edges` to `createLayers`.

**Step 3: Test in browser**

Run: `python3 -m http.server 8080`

Nodes should cluster based on import relationships rather than being in a grid.

**Step 4: Commit**

```bash
git add web/js/layout.js web/js/layers.js web/js/main.js
git commit -m "feat: force-directed layout for nodes within layers"
```

---

## Task 10: Render edges as bezier curves

**Files:**
- Create: `web/js/edges.js`
- Modify: `web/js/main.js`

**Step 1: Create web/js/edges.js**

```javascript
// web/js/edges.js
import * as THREE from 'three';

const EDGE_COLORS = {
    imports: 0x4488cc,
    calls: 0xcc8844,
    inherits_from: 0x8844cc,
    depends_on: 0x666666,
    contains: 0x333344,
};

export function createEdges(edges, nodeMeshes, scene) {
    const edgeMeshes = [];

    for (const edge of edges) {
        if (edge.type === 'contains') continue; // skip hierarchy edges

        const fromMesh = nodeMeshes[edge.from];
        const toMesh = nodeMeshes[edge.to];
        if (!fromMesh || !toMesh) continue;

        const start = fromMesh.position.clone();
        const end = toMesh.position.clone();

        // Control point: midpoint raised for cross-layer, offset for intra-layer
        const mid = start.clone().add(end).multiplyScalar(0.5);
        const isVertical = Math.abs(start.y - end.y) > 2;

        if (isVertical) {
            mid.x += (Math.random() - 0.5) * 4;
            mid.z += (Math.random() - 0.5) * 4;
        } else {
            mid.y += 3;
        }

        const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
        const points = curve.getPoints(20);
        const geometry = new THREE.BufferGeometry().setFromPoints(points);

        const color = EDGE_COLORS[edge.type] || 0x444444;
        const material = new THREE.LineBasicMaterial({
            color,
            transparent: true,
            opacity: 0.4,
        });

        const line = new THREE.Line(geometry, material);
        line.userData = { type: 'edge', edgeData: edge };
        scene.add(line);
        edgeMeshes.push(line);
    }

    return edgeMeshes;
}

export function highlightEdges(edgeMeshes, nodeId) {
    for (const line of edgeMeshes) {
        const edge = line.userData.edgeData;
        if (edge.from === nodeId || edge.to === nodeId) {
            line.material.opacity = 1.0;
            line.material.linewidth = 2;
        } else {
            line.material.opacity = 0.08;
        }
    }
}

export function resetEdgeHighlights(edgeMeshes) {
    for (const line of edgeMeshes) {
        line.material.opacity = 0.4;
        line.material.linewidth = 1;
    }
}
```

**Step 2: Update main.js to render edges**

```javascript
import { createEdges } from './edges.js';

// After createLayers:
const edgeMeshes = createEdges(graph.edges, nodeMeshes, scene);
```

**Step 3: Test in browser**

Colored bezier curves connecting nodes across and within layers.

**Step 4: Commit**

```bash
git add web/js/edges.js web/js/main.js
git commit -m "feat: render edges as colored bezier curves between nodes"
```

---

## Task 11: Hover interaction and info panel

**Files:**
- Create: `web/js/interaction.js`
- Modify: `web/js/main.js`

**Step 1: Create web/js/interaction.js**

```javascript
// web/js/interaction.js
import * as THREE from 'three';
import { highlightEdges, resetEdgeHighlights } from './edges.js';

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

export function setupInteraction(camera, scene, nodeDataMap, edgeMeshes, nodeMeshes) {
    const infoPanel = document.getElementById('info-panel');
    let hoveredMesh = null;
    const originalColors = new Map();

    window.addEventListener('mousemove', (event) => {
        mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);
        const meshes = Array.from(nodeDataMap.keys());
        const intersects = raycaster.intersectObjects(meshes);

        if (intersects.length > 0) {
            const mesh = intersects[0].object;
            if (mesh !== hoveredMesh) {
                // Reset previous
                if (hoveredMesh) {
                    const orig = originalColors.get(hoveredMesh);
                    if (orig) hoveredMesh.material.emissive.setHex(0x000000);
                    resetEdgeHighlights(edgeMeshes);
                    resetNodeOpacity(nodeMeshes);
                }

                hoveredMesh = mesh;
                originalColors.set(mesh, mesh.material.color.getHex());
                mesh.material.emissive.setHex(0x333333);

                const data = nodeDataMap.get(mesh);
                showInfoPanel(data);
                highlightEdges(edgeMeshes, data.id);
                fadeUnconnectedNodes(nodeMeshes, edgeMeshes, data.id);
            }
        } else if (hoveredMesh) {
            hoveredMesh.material.emissive.setHex(0x000000);
            hoveredMesh = null;
            infoPanel.style.display = 'none';
            resetEdgeHighlights(edgeMeshes);
            resetNodeOpacity(nodeMeshes);
        }
    });
}

function showInfoPanel(data) {
    const panel = document.getElementById('info-panel');
    document.getElementById('info-name').textContent = data.name;
    document.getElementById('info-type').textContent = data.type;
    document.getElementById('info-loc').textContent = data.lines_of_code;
    document.getElementById('info-lang').textContent = data.language || '—';
    document.getElementById('info-path').textContent = data.file_path;
    panel.style.display = 'block';
}

function fadeUnconnectedNodes(nodeMeshes, edgeMeshes, nodeId) {
    const connected = new Set([nodeId]);
    for (const line of edgeMeshes) {
        const edge = line.userData.edgeData;
        if (edge.from === nodeId) connected.add(edge.to);
        if (edge.to === nodeId) connected.add(edge.from);
    }
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        mesh.material.opacity = connected.has(id) ? 1.0 : 0.15;
        mesh.material.transparent = true;
    }
}

function resetNodeOpacity(nodeMeshes) {
    for (const mesh of Object.values(nodeMeshes)) {
        mesh.material.opacity = 1.0;
    }
}
```

**Step 2: Update main.js**

```javascript
import { setupInteraction } from './interaction.js';

// After edges are created:
setupInteraction(camera, scene, nodeDataMap, edgeMeshes, nodeMeshes);
```

**Step 3: Test in browser**

Hover over a block → info panel appears, connected edges highlight, unconnected nodes fade.

**Step 4: Commit**

```bash
git add web/js/interaction.js web/js/main.js
git commit -m "feat: hover interaction with info panel and edge highlighting"
```

---

## Task 12: Layer focus — click to switch vertical/horizontal view

**Files:**
- Modify: `web/js/interaction.js`
- Modify: `web/js/main.js`

**Step 1: Add click handler in interaction.js**

Add to `setupInteraction`:

```javascript
let focusedLayer = null;

window.addEventListener('click', (event) => {
    raycaster.setFromCamera(mouse, camera);

    // Check layer planes
    const layerPlanes = Object.values(layerMeshes);
    const layerHits = raycaster.intersectObjects(layerPlanes);

    if (layerHits.length > 0) {
        const layer = layerHits[0].object;
        const level = layer.userData.level;
        const y = layer.position.y;

        if (focusedLayer === level) {
            // Unfocus — back to vertical view
            focusedLayer = null;
            animateCamera(camera, controls, defaultCameraPos, defaultTarget);
        } else {
            // Focus this layer — horizontal view
            focusedLayer = level;
            const targetPos = new THREE.Vector3(LAYER_SIZE * 0.7, y + 5, LAYER_SIZE * 0.7);
            const targetLookAt = new THREE.Vector3(0, y, 0);
            animateCamera(camera, controls, targetPos, targetLookAt);
        }
        return;
    }
});

window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && focusedLayer !== null) {
        focusedLayer = null;
        animateCamera(camera, controls, defaultCameraPos, defaultTarget);
    }
});
```

Update the function signature to accept `layerMeshes`, `controls`, `animateCamera`, `defaultCameraPos`, `defaultTarget`.

**Step 2: Test in browser**

Click a layer plane → camera animates to horizontal view. Click again or press Escape → back to vertical.

**Step 3: Commit**

```bash
git add web/js/interaction.js web/js/main.js
git commit -m "feat: click layer to toggle vertical/horizontal camera view"
```

---

## Task 13: Serve from CLI

**Files:**
- Modify: `src/callgraph/cli.py`

**Step 1: Add serve subcommand to CLI**

```python
# Add to cli.py
import http.server
import functools

def serve(args):
    port = args.port
    directory = str(Path(__file__).parent.parent.parent / "web")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    with http.server.HTTPServer(("", port), handler) as httpd:
        print(f"Serving at http://localhost:{port}")
        httpd.serve_forever()
```

Add subcommand to argparse:
- `callgraph build <path>` — builds the graph
- `callgraph serve` — starts the web server

**Step 2: Test**

Run: `callgraph build test-project/ && callgraph serve`
Expected: Browser opens to visualization.

**Step 3: Commit**

```bash
git add src/callgraph/cli.py
git commit -m "feat: CLI serve command to launch web visualizer"
```

---

## Task 14: End-to-end integration test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
import json
import tempfile
from pathlib import Path
from callgraph.graph_builder import build_graph
from callgraph.output import write_graph

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_full_pipeline():
    graph = build_graph(TEST_PROJECT)

    with tempfile.TemporaryDirectory() as tmpdir:
        write_graph(graph, tmpdir)

        nodes = json.loads((Path(tmpdir) / "nodes.json").read_text())
        edges = json.loads((Path(tmpdir) / "edges.json").read_text())

    # Verify node types exist
    types = {n["type"] for n in nodes}
    assert "directory" in types
    assert "file" in types
    assert "function" in types
    assert "class" in types

    # Verify edge types exist
    edge_types = {e["type"] for e in edges}
    assert "contains" in edge_types
    assert "imports" in edge_types

    # Verify cross-language coverage
    languages = {n["language"] for n in nodes if n.get("language")}
    assert "python" in languages
    assert any(l in languages for l in ("typescript", "typescriptreact"))

    # Verify abstraction levels are assigned
    levels = {n["abstraction_level"] for n in nodes if n["type"] == "file"}
    assert 0 in levels  # models
    assert 1 in levels  # services
    assert 2 in levels  # api/components

    # Verify some known import edges
    import_edges = [(e["from"], e["to"]) for e in edges if e["type"] == "imports"]
    assert any("auth_routes" in f and "auth_service" in t for f, t in import_edges)

def test_node_ids_are_unique():
    graph = build_graph(TEST_PROJECT)
    ids = [n["id"] for n in graph["nodes"]]
    assert len(ids) == len(set(ids)), f"Duplicate node IDs found"

def test_edges_reference_valid_nodes():
    graph = build_graph(TEST_PROJECT)
    node_ids = {n["id"] for n in graph["nodes"]}
    for edge in graph["edges"]:
        assert edge["from"] in node_ids, f"Edge references unknown source: {edge['from']}"
        assert edge["to"] in node_ids, f"Edge references unknown target: {edge['to']}"
```

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: end-to-end integration tests for full pipeline"
```

---

## Summary

| Task | Component | Description |
|------|-----------|-------------|
| 1 | Setup | Project scaffolding, Python env, CLI entry point |
| 2 | Builder | File discovery and language detection |
| 3 | Builder | Python AST parsing (classes, functions, imports) |
| 4 | Builder | TypeScript/JS AST parsing |
| 5 | Builder | Graph assembly (nodes, edges, abstraction levels) |
| 6 | Builder | JSON output and CLI integration |
| 7 | Web | Three.js scene, camera, controls |
| 8 | Web | Load graph data and render layers with blocks |
| 9 | Web | Force-directed layout within layers |
| 10 | Web | Bezier curve edges between nodes |
| 11 | Web | Hover interaction and info panel |
| 12 | Web | Click to focus layer (vertical ↔ horizontal) |
| 13 | CLI | Serve command for web visualizer |
| 14 | Test | End-to-end integration test |
