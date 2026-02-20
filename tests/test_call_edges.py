from pathlib import Path
from callgraph.graph_builder import build_graph

TEST_PROJECT = Path(__file__).parent.parent / "test-project"


def test_same_file_python_calls():
    """register_user calls hash_password, authenticate_user calls verify_password"""
    graph = build_graph(TEST_PROJECT)
    calls = [(e["from"], e["to"]) for e in graph["edges"] if e["type"] == "calls"]
    assert any("register_user" in f and "hash_password" in t for f, t in calls), \
        f"Expected register_user -> hash_password call edge"
    assert any("authenticate_user" in f and "verify_password" in t for f, t in calls), \
        f"Expected authenticate_user -> verify_password call edge"


def test_cross_file_python_calls():
    """auth_routes.login calls authenticate_user and create_access_token from auth_service"""
    graph = build_graph(TEST_PROJECT)
    calls = [(e["from"], e["to"]) for e in graph["edges"] if e["type"] == "calls"]
    assert any("auth_routes" in f and "login" in f and "authenticate_user" in t for f, t in calls), \
        f"Expected login -> authenticate_user cross-file call edge"
    assert any("auth_routes" in f and "login" in f and "create_access_token" in t for f, t in calls), \
        f"Expected login -> create_access_token cross-file call edge"


def test_cross_file_typescript_calls():
    """useTasks calls fetchTasks, createTask etc from services/tasks"""
    graph = build_graph(TEST_PROJECT)
    calls = [(e["from"], e["to"]) for e in graph["edges"] if e["type"] == "calls"]
    assert any("useTasks" in f and "fetchTasks" in t for f, t in calls), \
        f"Expected useTasks -> fetchTasks cross-file call edge"


def test_call_edges_reference_valid_nodes():
    """All call edges should reference existing function nodes"""
    graph = build_graph(TEST_PROJECT)
    node_ids = {n["id"] for n in graph["nodes"]}
    call_edges = [e for e in graph["edges"] if e["type"] == "calls"]
    for edge in call_edges:
        assert edge["from"] in node_ids, f"Call edge source not found: {edge['from']}"
        assert edge["to"] in node_ids, f"Call edge target not found: {edge['to']}"
