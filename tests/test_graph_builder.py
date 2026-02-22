from pathlib import Path
from callgraph.graph_builder import build_graph

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_builds_directory_nodes():
    graph = build_graph(TEST_PROJECT)
    dir_nodes = [n for n in graph["nodes"] if n["type"] == "directory"]
    names = {n["name"] for n in dir_nodes}
    assert "gateway" in names
    assert "services" in names

def test_builds_file_nodes():
    graph = build_graph(TEST_PROJECT)
    file_nodes = [n for n in graph["nodes"] if n["type"] == "file"]
    names = {n["name"] for n in file_nodes}
    assert "service_registry.py" in names
    assert "App.tsx" in names

def test_builds_function_nodes():
    graph = build_graph(TEST_PROJECT)
    func_nodes = [n for n in graph["nodes"] if n["type"] == "function"]
    names = {n["name"] for n in func_nodes}
    assert len(names) > 0

def test_builds_contains_edges():
    graph = build_graph(TEST_PROJECT)
    contains = [e for e in graph["edges"] if e["type"] == "contains"]
    assert len(contains) > 0

def test_builds_imports_edges():
    graph = build_graph(TEST_PROJECT)
    imports = [e for e in graph["edges"] if e["type"] == "imports"]
    assert len(imports) > 0

def test_assigns_abstraction_level():
    graph = build_graph(TEST_PROJECT)
    func_nodes = [n for n in graph["nodes"] if n["type"] == "function"]
    for fn in func_nodes:
        assert fn["abstraction_level"] == 0

def test_nodes_have_language():
    graph = build_graph(TEST_PROJECT)
    file_nodes = [n for n in graph["nodes"] if n["type"] == "file"]
    for n in file_nodes:
        assert "language" in n
        assert n["language"] in ("python", "typescript", "typescriptreact", "javascript", "javascriptreact")

def test_all_nodes_have_role():
    graph = build_graph(TEST_PROJECT)
    for node in graph["nodes"]:
        assert "role" in node, f"Node {node['id']} missing role field"
        assert node["role"] in ("data", "control", "hybrid"), f"Node {node['id']} has invalid role: {node['role']}"

def test_interface_nodes_are_data():
    graph = build_graph(TEST_PROJECT)
    interfaces = [n for n in graph["nodes"] if n["type"] == "interface"]
    assert len(interfaces) > 0
    for n in interfaces:
        assert n["role"] == "data", f"Interface {n['name']} should be data, got {n['role']}"

def test_type_alias_nodes_are_data():
    graph = build_graph(TEST_PROJECT)
    type_aliases = [n for n in graph["nodes"] if n["type"] == "type_alias"]
    assert len(type_aliases) > 0
    for n in type_aliases:
        assert n["role"] == "data", f"Type alias {n['name']} should be data, got {n['role']}"

def test_dataclass_classified_as_data():
    graph = build_graph(TEST_PROJECT)
    node_map = {n["name"]: n for n in graph["nodes"] if n["type"] == "class"}
    assert "ServiceInstance" in node_map
    assert node_map["ServiceInstance"]["role"] == "data"

def test_basemodel_classified_as_data():
    graph = build_graph(TEST_PROJECT)
    node_map = {n["name"]: n for n in graph["nodes"] if n["type"] == "class"}
    assert "InviteMemberRequest" in node_map
    assert node_map["InviteMemberRequest"]["role"] == "data"

def test_enum_classified_as_data():
    graph = build_graph(TEST_PROJECT)
    node_map = {n["name"]: n for n in graph["nodes"] if n["type"] == "class"}
    assert "ServiceStatus" in node_map
    assert node_map["ServiceStatus"]["role"] == "data"

def test_plain_class_classified_as_hybrid():
    graph = build_graph(TEST_PROJECT)
    node_map = {n["name"]: n for n in graph["nodes"] if n["type"] == "class"}
    assert "AuthService" in node_map
    assert node_map["AuthService"]["role"] == "hybrid"

def test_file_role_majority_vote():
    graph = build_graph(TEST_PROJECT)
    file_nodes = [n for n in graph["nodes"] if n["type"] == "file"]
    for n in file_nodes:
        assert n["role"] in ("data", "control", "hybrid")
