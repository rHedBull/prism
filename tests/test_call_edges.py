from pathlib import Path
from callgraph.graph_builder import build_graph

TEST_PROJECT = Path(__file__).parent.parent / "test-project"


def test_same_file_python_calls():
    """invoice routes call helper functions in the same file"""
    graph = build_graph(TEST_PROJECT)
    calls = [(e["from"], e["to"]) for e in graph["edges"] if e["type"] == "calls"]
    assert any("get_invoice" in f and "_tenant_id_from_header" in t for f, t in calls), \
        f"Expected get_invoice -> _tenant_id_from_header call edge"


def test_same_file_typescript_calls():
    """useUnreadCount calls useNotifications in the same file"""
    graph = build_graph(TEST_PROJECT)
    calls = [(e["from"], e["to"]) for e in graph["edges"] if e["type"] == "calls"]
    assert any("useUnreadCount" in f and "useNotifications" in t for f, t in calls), \
        f"Expected useUnreadCount -> useNotifications call edge"


def test_call_edges_reference_valid_nodes():
    """All call edges should reference existing function nodes"""
    graph = build_graph(TEST_PROJECT)
    node_ids = {n["id"] for n in graph["nodes"]}
    call_edges = [e for e in graph["edges"] if e["type"] == "calls"]
    for edge in call_edges:
        assert edge["from"] in node_ids, f"Call edge source not found: {edge['from']}"
        assert edge["to"] in node_ids, f"Call edge target not found: {edge['to']}"
