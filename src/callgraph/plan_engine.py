"""Plan engine — reads plan JSON, applies operations to a graph copy, calls diff engine."""

import copy
import json
from pathlib import Path

from callgraph.graph_diff import compute_diff

LAYER_TO_LEVEL = {"C1": 3, "C2": 2, "C3": 1}


def apply_plan(graph: dict, plan: dict) -> dict:
    """Apply plan operations to a copy of the graph and return the diff.

    Args:
        graph: Current graph with 'nodes' and 'edges' lists.
        plan: Plan dict with 'name', 'description', and 'operations' list.

    Returns:
        Diff dict from compute_diff with meta.source='plan'.
    """
    modified = copy.deepcopy(graph)
    node_index = {n["id"]: n for n in modified["nodes"]}

    for op in plan.get("operations", []):
        action = op["op"]
        if action == "add":
            _apply_add(modified, node_index, op)
        elif action == "remove":
            _apply_remove(modified, node_index, op)
        elif action == "move":
            _apply_move(node_index, op)

    meta = {"source": "plan", "plan_name": plan.get("name", "unnamed")}
    return compute_diff(graph, modified, meta)


def load_plan(plan_path: str) -> dict:
    """Load a plan JSON file."""
    return json.loads(Path(plan_path).read_text())


def _apply_add(graph: dict, node_index: dict, op: dict):
    level = LAYER_TO_LEVEL.get(op.get("layer", "C2"), 2)
    name = op["name"]
    node_id = f"plan:{name.lower().replace(' ', '_')}"

    node = {
        "id": node_id,
        "type": "file",
        "name": name,
        "file_path": f"(planned)/{name}",
        "language": None,
        "lines_of_code": 0,
        "abstraction_level": level,
        "export_count": 0,
        "parent": None,
    }
    graph["nodes"].append(node)
    node_index[node_id] = node

    for dep_id in op.get("depends_on", []):
        if dep_id in node_index:
            graph["edges"].append({
                "from": node_id,
                "to": dep_id,
                "type": "imports",
                "weight": 1,
            })


def _apply_remove(graph: dict, node_index: dict, op: dict):
    target_id = op["id"]
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != target_id]
    graph["edges"] = [e for e in graph["edges"] if e["from"] != target_id and e["to"] != target_id]
    node_index.pop(target_id, None)


def _apply_move(node_index: dict, op: dict):
    target_id = op["id"]
    if target_id not in node_index:
        return
    new_level = LAYER_TO_LEVEL.get(op.get("to_layer", "C2"), 2)
    node_index[target_id]["abstraction_level"] = new_level
