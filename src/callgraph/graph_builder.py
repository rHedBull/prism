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

    # Build call edges (function-level)
    _build_call_edges(file_parse_results, files, edges)

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

def _build_call_edges(parse_results: dict, files: list, edges: list):
    file_paths = {f["path"] for f in files}

    # Build per-file symbol tables: name -> func node ID
    file_symbols = {}
    for file_path, result in parse_results.items():
        symbols = {}
        for node in result["nodes"]:
            if node["type"] == "function":
                symbols[node["name"]] = node["id"]
        file_symbols[file_path] = symbols

    # Build per-file import maps: imported_name -> (source_file, original_name)
    file_import_map = {}
    for file_path, result in parse_results.items():
        import_map = {}
        for imp in result["imports"]:
            target_file = _resolve_import(imp["module"], file_path, file_paths)
            if target_file:
                for name in imp.get("names", []):
                    import_map[name] = target_file
        file_import_map[file_path] = import_map

    # Emit call edges
    seen_call_edges = set()
    for file_path, result in parse_results.items():
        local_symbols = file_symbols.get(file_path, {})
        import_map = file_import_map.get(file_path, {})

        for node in result["nodes"]:
            if node["type"] != "function" or "calls" not in node:
                continue

            caller_id = node["id"]
            for call_name in node["calls"]:
                target_id = None

                # 1. Check same-file functions
                if call_name in local_symbols and local_symbols[call_name] != caller_id:
                    target_id = local_symbols[call_name]

                # 2. Check imported functions
                elif call_name in import_map:
                    target_file = import_map[call_name]
                    target_symbols = file_symbols.get(target_file, {})
                    if call_name in target_symbols:
                        target_id = target_symbols[call_name]

                if target_id and (caller_id, target_id) not in seen_call_edges:
                    seen_call_edges.add((caller_id, target_id))
                    edges.append({
                        "from": caller_id,
                        "to": target_id,
                        "type": "calls",
                        "weight": 1,
                    })
