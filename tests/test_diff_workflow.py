"""Integration test: build two graphs, diff them, verify output."""
import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def two_codebases(tmp_path):
    """Create two minimal Python codebases with a structural difference."""
    base = tmp_path / "base"
    (base / "service_a").mkdir(parents=True)
    (base / "service_a" / "__init__.py").write_text("")
    (base / "service_a" / "handler.py").write_text("def handle():\n    pass\n")

    changed = tmp_path / "changed"
    (changed / "service_a").mkdir(parents=True)
    (changed / "service_a" / "__init__.py").write_text("")
    (changed / "service_a" / "handler.py").write_text(
        "def handle():\n    return process()\n\ndef process():\n    pass\n"
    )
    (changed / "service_b").mkdir(parents=True)
    (changed / "service_b" / "__init__.py").write_text("")
    (changed / "service_b" / "api.py").write_text("def endpoint():\n    pass\n")

    return base, changed


def test_build_and_diff(two_codebases, tmp_path):
    """Build graphs for two codebases and diff them."""
    from callgraph.graph_builder import build_graph
    from callgraph.output import write_graph
    from callgraph.cli import cmd_diff
    import argparse

    base, changed = two_codebases

    # Build both
    graph_a = build_graph(base)
    write_graph(graph_a, str(base / ".callgraph"))

    graph_b = build_graph(changed)
    write_graph(graph_b, str(changed / ".callgraph"))

    # Diff
    args = argparse.Namespace(
        graph_a=str(base), graph_b=str(changed),
        output=str(tmp_path / "diff_out"),
        ref_a="base", ref_b="changed",
    )
    cmd_diff(args)

    diff = json.loads((tmp_path / "diff_out" / "diff.json").read_text())
    assert diff["summary"]["added_nodes"] > 0, "service_b should be added"
    assert diff["meta"]["ref_a"] == "base"
