"""Graph diff engine — compares two graph snapshots and produces a C3+ structural diff."""


def compute_diff(graph_a: dict, graph_b: dict, meta: dict | None = None) -> dict:
    """Compare two graph snapshots and return structural diff filtered to C3+ nodes.

    Args:
        graph_a: Base graph with 'nodes' and 'edges' lists.
        graph_b: Target graph with 'nodes' and 'edges' lists.
        meta: Optional metadata dict (source, ref_a, ref_b, plan_name, etc.).

    Returns:
        Diff dict with added/removed/moved/modified nodes and edges.
    """
    nodes_a = {n["id"]: n for n in graph_a["nodes"]}
    nodes_b = {n["id"]: n for n in graph_b["nodes"]}

    # Filter to C3+ (abstraction_level >= 1)
    filtered_a = {k: v for k, v in nodes_a.items() if v.get("abstraction_level", 0) >= 1}
    filtered_b = {k: v for k, v in nodes_b.items() if v.get("abstraction_level", 0) >= 1}

    ids_a = set(filtered_a.keys())
    ids_b = set(filtered_b.keys())

    # Straight added/removed
    purely_added_ids = ids_b - ids_a
    purely_removed_ids = ids_a - ids_b

    # Move detection: removed node with same name appears at different path
    moved_nodes = []
    remaining_added = set(purely_added_ids)
    remaining_removed = set(purely_removed_ids)

    removed_by_name = {}
    for rid in purely_removed_ids:
        name = filtered_a[rid]["name"]
        removed_by_name.setdefault(name, []).append(rid)

    for aid in purely_added_ids:
        name = filtered_b[aid]["name"]
        if name in removed_by_name and removed_by_name[name]:
            rid = removed_by_name[name].pop(0)
            moved_nodes.append({
                "id": aid,
                "old_id": rid,
                "name": name,
                "old_file_path": filtered_a[rid].get("file_path"),
                "new_file_path": filtered_b[aid].get("file_path"),
                "abstraction_level": filtered_b[aid].get("abstraction_level", 0),
            })
            remaining_added.discard(aid)
            remaining_removed.discard(rid)

    added_nodes = [_node_summary(filtered_b[nid]) for nid in sorted(remaining_added)]
    removed_nodes = [_node_summary(filtered_a[nid]) for nid in sorted(remaining_removed)]

    # Modified detection: same id, different properties
    common_ids = ids_a & ids_b
    modified_nodes = []
    for nid in sorted(common_ids):
        changes = _detect_changes(filtered_a[nid], filtered_b[nid])
        if changes:
            modified_nodes.append({"id": nid, "changes": changes})

    # Edge matching by (from, to, type) tuple
    edges_a = {(e["from"], e["to"], e["type"]) for e in graph_a["edges"]}
    edges_b = {(e["from"], e["to"], e["type"]) for e in graph_b["edges"]}

    # Filter edges to only those connecting C3+ nodes
    all_c3_ids = set(filtered_a.keys()) | set(filtered_b.keys())
    edges_a_filtered = {e for e in edges_a if e[0] in all_c3_ids and e[1] in all_c3_ids}
    edges_b_filtered = {e for e in edges_b if e[0] in all_c3_ids and e[1] in all_c3_ids}

    added_edges = [{"from": e[0], "to": e[1], "type": e[2]} for e in sorted(edges_b_filtered - edges_a_filtered)]
    removed_edges = [{"from": e[0], "to": e[1], "type": e[2]} for e in sorted(edges_a_filtered - edges_b_filtered)]

    result = {
        "meta": meta or {},
        "summary": {
            "added_nodes": len(added_nodes),
            "removed_nodes": len(removed_nodes),
            "moved_nodes": len(moved_nodes),
            "modified_nodes": len(modified_nodes),
            "added_edges": len(added_edges),
            "removed_edges": len(removed_edges),
        },
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "moved_nodes": moved_nodes,
        "modified_nodes": modified_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
    }
    return result


def _node_summary(node: dict) -> dict:
    return {
        "id": node["id"],
        "name": node.get("name", ""),
        "abstraction_level": node.get("abstraction_level", 0),
        "lines_of_code": node.get("lines_of_code", 0),
    }


def _detect_changes(node_a: dict, node_b: dict) -> dict:
    """Compare two versions of the same node, return dict of changed fields."""
    changes = {}
    for field in ("lines_of_code", "export_count", "abstraction_level"):
        val_a = node_a.get(field)
        val_b = node_b.get(field)
        if val_a != val_b and val_a is not None and val_b is not None:
            changes[field] = [val_a, val_b]
    return changes
