import json
from pathlib import Path

import pytest


def test_cli_plan_produces_diff_json(tmp_path):
    """callgraph plan <plan.json> --graph-dir <dir> should write diff.json."""
    # Create a minimal graph
    graph_dir = tmp_path / "project" / ".callgraph"
    graph_dir.mkdir(parents=True)

    node = {"id": "dir:auth-service", "name": "auth-service", "type": "directory",
            "file_path": "auth-service", "abstraction_level": 2,
            "lines_of_code": 0, "export_count": 0, "parent": None}
    (graph_dir / "nodes.json").write_text(json.dumps([node]))
    (graph_dir / "edges.json").write_text(json.dumps([]))

    # Create a plan
    plan = {
        "name": "Test Plan",
        "description": "Add a service",
        "operations": [
            {"op": "add", "name": "rate_limiter.py", "layer": "C3",
             "depends_on": ["dir:auth-service"]}
        ]
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    from callgraph.cli import cmd_plan
    import argparse
    args = argparse.Namespace(
        plan=str(plan_path),
        graph_dir=str(tmp_path / "project"),
        output=str(tmp_path / "out"),
    )
    cmd_plan(args)

    diff_path = tmp_path / "out" / "diff.json"
    assert diff_path.exists()
    diff = json.loads(diff_path.read_text())
    assert diff["meta"]["source"] == "plan"
    assert diff["meta"]["plan_name"] == "Test Plan"
    assert diff["summary"]["added_nodes"] >= 1

    # Also writes plan.json copy
    assert (tmp_path / "out" / "plan.json").exists()
