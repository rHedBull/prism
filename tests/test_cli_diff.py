import json
import subprocess
from pathlib import Path

import pytest

from callgraph.graph_diff import compute_diff


def test_cli_diff_produces_diff_json(tmp_path, monkeypatch):
    """callgraph diff <dir_a> <dir_b> should write diff.json to output dir."""
    # Create two minimal graph dirs
    dir_a = tmp_path / "a" / ".callgraph"
    dir_b = tmp_path / "b" / ".callgraph"
    dir_a.mkdir(parents=True)
    dir_b.mkdir(parents=True)

    node = {"id": "file:x.py", "name": "x.py", "type": "file",
            "file_path": "x.py", "abstraction_level": 2,
            "lines_of_code": 50, "export_count": 1, "parent": None}
    node_b = {**node, "lines_of_code": 80}

    (dir_a / "nodes.json").write_text(json.dumps([node]))
    (dir_a / "edges.json").write_text(json.dumps([]))
    (dir_b / "nodes.json").write_text(json.dumps([node_b]))
    (dir_b / "edges.json").write_text(json.dumps([]))

    # Run CLI
    from callgraph.cli import cmd_diff
    import argparse
    args = argparse.Namespace(
        graph_a=str(dir_a.parent),
        graph_b=str(dir_b.parent),
        output=str(tmp_path / "out"),
        ref_a="aaa",
        ref_b="bbb",
    )
    cmd_diff(args)

    diff_path = tmp_path / "out" / "diff.json"
    assert diff_path.exists()
    diff = json.loads(diff_path.read_text())
    assert diff["summary"]["modified_nodes"] == 1
    assert diff["meta"]["source"] == "commits"
    assert diff["meta"]["ref_a"] == "aaa"
    assert diff["meta"]["ref_b"] == "bbb"
