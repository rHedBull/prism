# /diff and /impact Skills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Two Claude Code skills — `/diff` compares graph structure between git refs, `/impact` visualizes planned changes from a spec document.

**Architecture:** `/diff` is a mechanical bash workflow (worktree + build + diff). `/impact` requires Claude intelligence to parse specs into plan operations. Both produce `.callgraph/diff.json` for the viewer. The CLI gets a `diff` subcommand so `/diff` can shell out to it.

**Tech Stack:** Python (callgraph CLI), Claude Code skills (markdown commands), git worktrees

---

### Task 1: Add `callgraph diff` CLI subcommand

**Files:**
- Modify: `src/callgraph/cli.py`
- Test: `tests/test_cli_diff.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_diff.py
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_diff.py::test_cli_diff_produces_diff_json -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_diff'`

**Step 3: Implement cmd_diff in cli.py**

Add to `src/callgraph/cli.py`:

```python
def cmd_diff(args):
    """Compare two graph directories and write diff.json."""
    import json
    from callgraph.graph_diff import compute_diff

    dir_a = Path(args.graph_a) / ".callgraph"
    dir_b = Path(args.graph_b) / ".callgraph"

    graph_a = {
        "nodes": json.loads((dir_a / "nodes.json").read_text()),
        "edges": json.loads((dir_a / "edges.json").read_text()),
    }
    graph_b = {
        "nodes": json.loads((dir_b / "nodes.json").read_text()),
        "edges": json.loads((dir_b / "edges.json").read_text()),
    }

    meta = {
        "source": "commits",
        "ref_a": getattr(args, "ref_a", "unknown"),
        "ref_b": getattr(args, "ref_b", "unknown"),
    }
    diff = compute_diff(graph_a, graph_b, meta)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "diff.json").write_text(json.dumps(diff, indent=2))

    s = diff["summary"]
    print(f"Diff written to {out}/diff.json")
    print(f"  +{s['added_nodes']} added, -{s['removed_nodes']} removed, "
          f"~{s['modified_nodes']} modified, >{s['moved_nodes']} moved")
```

Wire into argparse in `main()`:

```python
    # diff subcommand
    diff_parser = subparsers.add_parser("diff", help="Compare two graph directories")
    diff_parser.add_argument("graph_a", help="Path to first codebase (with .callgraph/)")
    diff_parser.add_argument("graph_b", help="Path to second codebase (with .callgraph/)")
    diff_parser.add_argument("-o", "--output", default=".callgraph", help="Output directory for diff.json")
    diff_parser.add_argument("--ref-a", default="unknown", help="Label for graph_a")
    diff_parser.add_argument("--ref-b", default="unknown", help="Label for graph_b")
```

And in the dispatch:

```python
    elif args.command == "diff":
        cmd_diff(args)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_diff.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/callgraph/cli.py tests/test_cli_diff.py
git commit -m "feat: add callgraph diff CLI subcommand"
```

---

### Task 2: Create `/diff` Claude Code command

**Files:**
- Create: `.claude/commands/diff.md`

**Step 1: Create the .claude/commands directory**

```bash
mkdir -p .claude/commands
```

**Step 2: Write the /diff command**

Create `.claude/commands/diff.md`:

```markdown
---
description: "Compare callgraph structure between git refs and write diff.json for the viewer"
---

# /diff — Git Graph Comparison

Compare the callgraph between two git states. Produces `.callgraph/diff.json` for the prism viewer.

## Arguments

The user provides a git ref or ref range:
- `/diff main` — compare main..HEAD
- `/diff v1.0..feature/auth` — compare two specific refs

Parse the input:
- Single ref: ref_a = that ref, ref_b = current working directory
- Two refs with `..`: ref_a = left side, ref_b = right side

## Steps

1. **Parse refs** from the user's input. Default: ref_a = `main`, ref_b = current working dir.

2. **Ensure current graph is built:**
   ```bash
   callgraph build . -o .callgraph
   ```

3. **Create a temporary git worktree for ref_a:**
   ```bash
   git worktree add /tmp/prism-diff-$(date +%s) <ref_a>
   ```
   Save the worktree path.

4. **Build graph for ref_a:**
   ```bash
   callgraph build <worktree_path> -o <worktree_path>/.callgraph
   ```

5. **Run diff:**
   ```bash
   callgraph diff <worktree_path> . -o .callgraph --ref-a <ref_a> --ref-b <ref_b>
   ```

6. **Clean up worktree:**
   ```bash
   git worktree remove <worktree_path>
   ```

7. **Report results.** Print the diff summary. Tell the user:
   - `diff.json` has been written to `.callgraph/diff.json`
   - Run `callgraph serve` or reload the viewer to see the visual diff

## Error Handling

- If the ref doesn't exist, report the error and suggest `git branch -a` to list available refs.
- If `callgraph build` fails, report which path failed.
- Always clean up the worktree, even on error.
```

**Step 3: Test the command exists**

Run: `ls -la .claude/commands/diff.md`
Expected: File exists with correct content.

**Step 4: Commit**

```bash
git add .claude/commands/diff.md
git commit -m "feat: add /diff Claude Code command"
```

---

### Task 3: Add `callgraph plan` CLI subcommand

**Files:**
- Modify: `src/callgraph/cli.py`
- Test: `tests/test_cli_plan.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_plan.py
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_plan.py::test_cli_plan_produces_diff_json -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_plan'`

**Step 3: Implement cmd_plan in cli.py**

Add to `src/callgraph/cli.py`:

```python
def cmd_plan(args):
    """Apply a plan to a graph and write diff.json."""
    import json
    import shutil
    from callgraph.plan_engine import apply_plan, load_plan

    graph_dir = Path(args.graph_dir) / ".callgraph"
    graph = {
        "nodes": json.loads((graph_dir / "nodes.json").read_text()),
        "edges": json.loads((graph_dir / "edges.json").read_text()),
    }

    plan = load_plan(args.plan)
    diff = apply_plan(graph, plan)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "diff.json").write_text(json.dumps(diff, indent=2))
    shutil.copy2(args.plan, out / "plan.json")

    s = diff["summary"]
    print(f"Plan '{plan.get('name', 'unnamed')}' applied.")
    print(f"  +{s['added_nodes']} added, -{s['removed_nodes']} removed, "
          f"~{s['modified_nodes']} modified, >{s['moved_nodes']} moved")
    print(f"Output: {out}/diff.json")
```

Wire into argparse in `main()`:

```python
    # plan subcommand
    plan_parser = subparsers.add_parser("plan", help="Apply an architectural plan and produce diff")
    plan_parser.add_argument("plan", help="Path to plan.json")
    plan_parser.add_argument("--graph-dir", default=".", help="Path to codebase with .callgraph/")
    plan_parser.add_argument("-o", "--output", default=".callgraph", help="Output directory for diff.json")
```

And in dispatch:

```python
    elif args.command == "plan":
        cmd_plan(args)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_plan.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/callgraph/cli.py tests/test_cli_plan.py
git commit -m "feat: add callgraph plan CLI subcommand"
```

---

### Task 4: Create `/impact` Claude Code command

**Files:**
- Create: `.claude/commands/impact.md`

**Step 1: Write the /impact command**

Create `.claude/commands/impact.md`:

```markdown
---
description: "Visualize the structural impact of a planned change from a spec or design document"
---

# /impact — Plan Impact Visualization

Read a spec/design document, extract planned changes, and produce a visual diff showing the impact on the callgraph.

## Arguments

The user provides a path to a spec document:
- `/impact docs/plans/add-payment-gateway.md`
- `/impact` — prompts for file path

## Steps

1. **Read the spec document** provided by the user.

2. **Load the current graph** to understand what exists:
   ```bash
   cat .callgraph/nodes.json | python3 -c "
   import json, sys
   nodes = json.load(sys.stdin)
   for n in nodes:
       if n.get('abstraction_level', 0) >= 1:
           print(f'{n[\"id\"]}  ({n[\"type\"]}, level={n[\"abstraction_level\"]})')
   "
   ```
   If `.callgraph/` doesn't exist, build it first: `callgraph build .`

3. **Analyze the spec** and extract structural changes. Look for:
   - "Files affected" or "Changes" sections
   - New services, modules, or files to add
   - Existing files to remove or deprecate
   - Files moving between services (refactors)
   - Modified files (scope/size changes)

4. **Generate plan.json** by mapping spec findings to operations:
   - For each new file/service: `{"op": "add", "name": "<name>", "layer": "C2|C3", "depends_on": ["<existing-node-id>"]}`
   - For each removal: `{"op": "remove", "id": "<existing-node-id>"}`
   - For each move: `{"op": "move", "id": "<existing-node-id>", "to_layer": "C2|C3"}`

   **Layer mapping:**
   - C1 (level 3) = System context (rare to add)
   - C2 (level 2) = Services, top-level directories
   - C3 (level 1) = Components, leaf directories, individual files

   **Important:** Match node IDs to existing graph nodes. Node IDs follow the pattern:
   - `dir:<path>` for directories (e.g. `dir:auth-service`, `dir:auth-service/services`)
   - `file:<path>` for files (e.g. `file:auth-service/main.py`)

   Write the plan to `.callgraph/plan.json`.

5. **Apply the plan:**
   ```bash
   callgraph plan .callgraph/plan.json --graph-dir . -o .callgraph
   ```

6. **Report results.** Print:
   - The plan operations you generated (summary)
   - The diff summary (added/removed/modified/moved counts)
   - Tell the user: `diff.json` written, reload viewer to see impact

## Example

Given a spec that says "Replace billing-service with a new payment-gateway service that depends on auth-service":

```json
{
  "name": "Replace Billing with Payment Gateway",
  "operations": [
    {"op": "remove", "id": "dir:billing-service"},
    {"op": "add", "name": "payment-gateway", "layer": "C2", "depends_on": ["dir:auth-service"]},
    {"op": "add", "name": "payment_handler.py", "layer": "C3", "depends_on": ["dir:auth-service"]}
  ]
}
```

## Tips

- Removing a C2 directory cascades to all its C3/C4 children automatically
- Adding a child under an existing parent marks the parent as modified
- When in doubt about layer, use C3 for files and C2 for services/directories
- The plan engine handles cascading — just specify the top-level operations
```

**Step 2: Test the command exists**

Run: `ls -la .claude/commands/impact.md`
Expected: File exists with correct content.

**Step 3: Commit**

```bash
git add .claude/commands/impact.md
git commit -m "feat: add /impact Claude Code command"
```

---

### Task 5: Integration test — full /diff workflow

**Files:**
- Test: `tests/test_diff_workflow.py`

**Step 1: Write the integration test**

```python
# tests/test_diff_workflow.py
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
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_diff_workflow.py -v`
Expected: PASS (depends on Tasks 1 being done)

**Step 3: Commit**

```bash
git add tests/test_diff_workflow.py
git commit -m "test: integration test for build + diff workflow"
```

---

### Task 6: Run full test suite and verify

**Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass including new ones.

**Step 2: Verify commands are discoverable**

```bash
callgraph diff --help
callgraph plan --help
ls .claude/commands/
```

**Step 3: Manual smoke test of /diff**

```bash
# Build current graph
callgraph build test-project -o .callgraph

# The /diff command would do this via worktrees, but we can test the CLI directly:
callgraph diff . . -o /tmp/test-diff --ref-a HEAD~1 --ref-b HEAD
cat /tmp/test-diff/diff.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d['summary'], indent=2))"
```

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address issues from integration testing"
```
