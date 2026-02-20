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
