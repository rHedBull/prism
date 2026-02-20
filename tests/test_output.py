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
