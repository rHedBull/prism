from callgraph.graph_diff import compute_diff


def _make_node(id, name="test", abstraction_level=2, lines_of_code=100, export_count=5, file_path=None):
    return {
        "id": id,
        "name": name,
        "type": "file",
        "file_path": file_path or id.replace("file:", ""),
        "abstraction_level": abstraction_level,
        "lines_of_code": lines_of_code,
        "export_count": export_count,
    }


def _make_edge(from_id, to_id, type="imports"):
    return {"from": from_id, "to": to_id, "type": type, "weight": 1}


def test_no_changes():
    node = _make_node("file:a.py", "a.py")
    graph = {"nodes": [node], "edges": []}
    diff = compute_diff(graph, graph)
    assert diff["summary"]["added_nodes"] == 0
    assert diff["summary"]["removed_nodes"] == 0
    assert diff["summary"]["modified_nodes"] == 0


def test_added_node():
    graph_a = {"nodes": [_make_node("file:a.py", "a.py")], "edges": []}
    graph_b = {"nodes": [_make_node("file:a.py", "a.py"), _make_node("file:b.py", "b.py")], "edges": []}
    diff = compute_diff(graph_a, graph_b)
    assert diff["summary"]["added_nodes"] == 1
    assert diff["added_nodes"][0]["id"] == "file:b.py"


def test_removed_node():
    graph_a = {"nodes": [_make_node("file:a.py", "a.py"), _make_node("file:b.py", "b.py")], "edges": []}
    graph_b = {"nodes": [_make_node("file:a.py", "a.py")], "edges": []}
    diff = compute_diff(graph_a, graph_b)
    assert diff["summary"]["removed_nodes"] == 1
    assert diff["removed_nodes"][0]["id"] == "file:b.py"


def test_modified_node():
    node_a = _make_node("file:a.py", "a.py", lines_of_code=100)
    node_b = _make_node("file:a.py", "a.py", lines_of_code=200)
    diff = compute_diff({"nodes": [node_a], "edges": []}, {"nodes": [node_b], "edges": []})
    assert diff["summary"]["modified_nodes"] == 1
    assert diff["modified_nodes"][0]["changes"]["lines_of_code"] == [100, 200]


def test_moved_node():
    """Node disappears from one path, same name appears at another — classified as moved."""
    node_a = _make_node("file:old/foo.py", "foo.py", file_path="old/foo.py")
    node_b = _make_node("file:new/foo.py", "foo.py", file_path="new/foo.py")
    diff = compute_diff({"nodes": [node_a], "edges": []}, {"nodes": [node_b], "edges": []})
    assert diff["summary"]["moved_nodes"] == 1
    assert diff["summary"]["added_nodes"] == 0
    assert diff["summary"]["removed_nodes"] == 0


def test_added_edge():
    nodes = [_make_node("file:a.py", "a.py"), _make_node("file:b.py", "b.py")]
    graph_a = {"nodes": nodes, "edges": []}
    graph_b = {"nodes": nodes, "edges": [_make_edge("file:a.py", "file:b.py")]}
    diff = compute_diff(graph_a, graph_b)
    assert diff["summary"]["added_edges"] == 1


def test_removed_edge():
    nodes = [_make_node("file:a.py", "a.py"), _make_node("file:b.py", "b.py")]
    graph_a = {"nodes": nodes, "edges": [_make_edge("file:a.py", "file:b.py")]}
    graph_b = {"nodes": nodes, "edges": []}
    diff = compute_diff(graph_a, graph_b)
    assert diff["summary"]["removed_edges"] == 1


def test_c4_nodes_filtered_out():
    """Nodes with abstraction_level 0 should not appear in diff output."""
    c4_node = _make_node("func:a.py:foo", "foo", abstraction_level=0)
    c2_node = _make_node("file:a.py", "a.py", abstraction_level=2)
    graph_a = {"nodes": [c2_node], "edges": []}
    graph_b = {"nodes": [c2_node, c4_node], "edges": []}
    diff = compute_diff(graph_a, graph_b)
    assert diff["summary"]["added_nodes"] == 0


def test_meta_passthrough():
    graph = {"nodes": [], "edges": []}
    meta = {"source": "commits", "ref_a": "main", "ref_b": "dev"}
    diff = compute_diff(graph, graph, meta)
    assert diff["meta"]["source"] == "commits"
    assert diff["meta"]["ref_a"] == "main"


def test_edge_filtering_c3_only():
    """Edges between C4 nodes should not appear in diff."""
    c4_a = _make_node("func:a.py:foo", "foo", abstraction_level=0)
    c4_b = _make_node("func:b.py:bar", "bar", abstraction_level=0)
    c2 = _make_node("file:a.py", "a.py", abstraction_level=2)
    graph_a = {"nodes": [c4_a, c4_b, c2], "edges": []}
    graph_b = {"nodes": [c4_a, c4_b, c2], "edges": [_make_edge("func:a.py:foo", "func:b.py:bar", "calls")]}
    diff = compute_diff(graph_a, graph_b)
    assert diff["summary"]["added_edges"] == 0
