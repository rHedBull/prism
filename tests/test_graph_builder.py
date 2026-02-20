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
