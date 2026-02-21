import json
import tempfile
from pathlib import Path

from callgraph.plan_engine import apply_plan, load_plan


def _make_node(id, name="test", abstraction_level=2, lines_of_code=100):
    return {
        "id": id,
        "name": name,
        "type": "file",
        "file_path": id.replace("file:", ""),
        "abstraction_level": abstraction_level,
        "lines_of_code": lines_of_code,
        "export_count": 3,
        "parent": None,
    }


def _make_edge(from_id, to_id, type="imports"):
    return {"from": from_id, "to": to_id, "type": type, "weight": 1}


def _base_graph():
    return {
        "nodes": [
            _make_node("file:services/user.py", "user.py"),
            _make_node("file:models/order.py", "order.py", abstraction_level=1),
        ],
        "edges": [
            _make_edge("file:services/user.py", "file:models/order.py"),
        ],
    }


def test_add_operation():
    graph = _base_graph()
    plan = {
        "name": "test-add",
        "operations": [
            {
                "op": "add",
                "name": "PaymentService",
                "layer": "C2",
                "depends_on": ["file:services/user.py"],
            }
        ],
    }
    diff = apply_plan(graph, plan)
    assert diff["summary"]["added_nodes"] == 1
    assert diff["added_nodes"][0]["name"] == "PaymentService"
    assert diff["summary"]["added_edges"] >= 1
    assert diff["meta"]["source"] == "plan"
    assert diff["meta"]["plan_name"] == "test-add"


def test_remove_operation():
    graph = _base_graph()
    plan = {
        "name": "test-remove",
        "operations": [
            {"op": "remove", "id": "file:models/order.py"},
        ],
    }
    diff = apply_plan(graph, plan)
    assert diff["summary"]["removed_nodes"] == 1
    assert diff["removed_nodes"][0]["id"] == "file:models/order.py"
    # Edge to removed node should also be gone
    assert diff["summary"]["removed_edges"] >= 1


def test_move_operation():
    graph = _base_graph()
    plan = {
        "name": "test-move",
        "operations": [
            {"op": "move", "id": "file:models/order.py", "to_layer": "C2"},
        ],
    }
    diff = apply_plan(graph, plan)
    # order.py was level 1, now level 2 — should show as modified
    assert diff["summary"]["modified_nodes"] == 1
    assert diff["modified_nodes"][0]["id"] == "file:models/order.py"
    assert diff["modified_nodes"][0]["changes"]["abstraction_level"] == [1, 2]


def test_add_with_layer_mapping():
    graph = _base_graph()
    plan = {
        "name": "test-layers",
        "operations": [
            {"op": "add", "name": "Gateway", "layer": "C1"},
        ],
    }
    diff = apply_plan(graph, plan)
    added = diff["added_nodes"][0]
    assert added["abstraction_level"] == 3  # C1 maps to level 3


def test_load_plan():
    plan_data = {"name": "test", "operations": []}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(plan_data, f)
        f.flush()
        loaded = load_plan(f.name)
    assert loaded["name"] == "test"


def test_add_nonexistent_dependency():
    """Adding a node with a depends_on pointing to nonexistent node should not crash."""
    graph = _base_graph()
    plan = {
        "name": "test-bad-dep",
        "operations": [
            {"op": "add", "name": "Orphan", "layer": "C2", "depends_on": ["file:nonexistent.py"]},
        ],
    }
    diff = apply_plan(graph, plan)
    assert diff["summary"]["added_nodes"] == 1
    # No edge created since target doesn't exist
    assert diff["summary"]["added_edges"] == 0


def test_remove_nonexistent_node():
    """Removing a node that doesn't exist should not crash."""
    graph = _base_graph()
    plan = {
        "name": "test-bad-remove",
        "operations": [
            {"op": "remove", "id": "file:nonexistent.py"},
        ],
    }
    diff = apply_plan(graph, plan)
    assert diff["summary"]["removed_nodes"] == 0


def test_original_graph_not_mutated():
    """apply_plan should deep-copy the graph, not mutate the original."""
    graph = _base_graph()
    original_node_count = len(graph["nodes"])
    plan = {
        "name": "test-immutable",
        "operations": [
            {"op": "add", "name": "NewThing", "layer": "C2"},
        ],
    }
    apply_plan(graph, plan)
    assert len(graph["nodes"]) == original_node_count
