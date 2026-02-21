"""Graph diff engine — compares two graph snapshots and produces a structural diff.

Cascading rules:
  - Removing a parent cascades removal to all descendants.
  - Adding a child under an existing parent marks the parent as modified.
  - Removing a child from an existing parent marks the parent as modified.
  - Each node appears in exactly one category (added > removed > moved > modified).
"""


def compute_diff(graph_a: dict, graph_b: dict, meta: dict | None = None) -> dict:
    """Compare two graph snapshots and return structural diff.

    Args:
        graph_a: Base graph with 'nodes' and 'edges' lists.
        graph_b: Target graph with 'nodes' and 'edges' lists.
        meta: Optional metadata dict (source, ref_a, ref_b, plan_name, etc.).

    Returns:
        Diff dict with added/removed/moved/modified nodes and edges.
    """
    nodes_a = {n["id"]: n for n in graph_a["nodes"]}
    nodes_b = {n["id"]: n for n in graph_b["nodes"]}

    ids_a = set(nodes_a.keys())
    ids_b = set(nodes_b.keys())

    # --- Build parent->children maps for cascading ---
    children_a = _build_children_map(graph_a["nodes"])
    children_b = _build_children_map(graph_b["nodes"])

    # --- Raw added/removed ---
    raw_added_ids = ids_b - ids_a
    raw_removed_ids = ids_a - ids_b

    # --- Cascade removals: if a node is removed, all its descendants are too ---
    cascaded_removed = set()
    for rid in raw_removed_ids:
        cascaded_removed.add(rid)
        cascaded_removed.update(_get_descendants(rid, children_a))
    # Only keep IDs that were actually in graph_a
    cascaded_removed &= ids_a

    # --- Cascade additions: if a node is added, all its descendants are too ---
    cascaded_added = set()
    for aid in raw_added_ids:
        cascaded_added.add(aid)
        cascaded_added.update(_get_descendants(aid, children_b))
    cascaded_added &= ids_b

    # --- Move detection: removed + added with same name ---
    moved_nodes = []
    remaining_added = set(cascaded_added)
    remaining_removed = set(cascaded_removed)

    removed_by_name = {}
    for rid in cascaded_removed:
        name = nodes_a[rid]["name"]
        removed_by_name.setdefault(name, []).append(rid)

    for aid in sorted(cascaded_added):
        name = nodes_b[aid]["name"]
        if name in removed_by_name and removed_by_name[name]:
            rid = removed_by_name[name].pop(0)
            moved_nodes.append({
                "id": aid,
                "old_id": rid,
                "name": name,
                "old_file_path": nodes_a[rid].get("file_path"),
                "new_file_path": nodes_b[aid].get("file_path"),
                "abstraction_level": nodes_b[aid].get("abstraction_level", 0),
            })
            remaining_added.discard(aid)
            remaining_removed.discard(rid)

    added_nodes = [_node_summary(nodes_b[nid]) for nid in sorted(remaining_added)]
    removed_nodes = [_node_summary(nodes_a[nid]) for nid in sorted(remaining_removed)]

    # --- Modified detection: same id, different properties ---
    already_categorized = remaining_added | remaining_removed | {m["id"] for m in moved_nodes} | {m.get("old_id") for m in moved_nodes}
    common_ids = (ids_a & ids_b) - already_categorized
    modified_nodes = []
    for nid in sorted(common_ids):
        changes = _detect_changes(nodes_a[nid], nodes_b[nid])
        if changes:
            modified_nodes.append({"id": nid, "changes": changes})

    # --- Bubble modifications upward ---
    # If a child is added/removed/modified, mark its existing parent as modified
    modified_ids = {m["id"] for m in modified_nodes}
    all_changed_ids = remaining_added | remaining_removed | modified_ids | {m["id"] for m in moved_nodes}

    for cid in list(all_changed_ids):
        # Walk up parent chain in whichever graph the node exists in
        node = nodes_b.get(cid) or nodes_a.get(cid)
        if not node:
            continue
        pid = node.get("parent")
        while pid:
            if pid in already_categorized or pid in modified_ids:
                break
            # Parent exists in both graphs and isn't already changed
            if pid in ids_a and pid in ids_b and pid not in all_changed_ids:
                modified_ids.add(pid)
                modified_nodes.append({
                    "id": pid,
                    "changes": {"children_changed": [True, True]},
                })
                all_changed_ids.add(pid)
            parent_node = nodes_b.get(pid) or nodes_a.get(pid)
            pid = parent_node.get("parent") if parent_node else None

    # --- Edge diff ---
    edges_a = {(e["from"], e["to"], e["type"]) for e in graph_a["edges"]}
    edges_b = {(e["from"], e["to"], e["type"]) for e in graph_b["edges"]}

    added_edges = [{"from": e[0], "to": e[1], "type": e[2]} for e in sorted(edges_b - edges_a)]
    removed_edges = [{"from": e[0], "to": e[1], "type": e[2]} for e in sorted(edges_a - edges_b)]

    return {
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


def _build_children_map(nodes: list) -> dict:
    """Build parent_id -> [child_ids] map."""
    children = {}
    for n in nodes:
        pid = n.get("parent")
        if pid:
            children.setdefault(pid, []).append(n["id"])
    return children


def _get_descendants(node_id: str, children_map: dict) -> set:
    """Get all descendants of a node recursively."""
    result = set()
    stack = list(children_map.get(node_id, []))
    while stack:
        cid = stack.pop()
        if cid not in result:
            result.add(cid)
            stack.extend(children_map.get(cid, []))
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
