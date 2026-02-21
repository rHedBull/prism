# Diff and Impact Skills Design

## Overview

Two Claude Code skills for the prism callgraph viewer:
- **`/diff <ref>`** — Compare graph structure between git states
- **`/impact <spec-file>`** — Visualize impact of a planned change from a spec document

Both produce `.callgraph/diff.json` which the viewer renders as a colored overlay.

## Skill 1: `/diff`

### Trigger
```
/diff main
/diff feature/auth..main
```

Single ref means `<ref>..HEAD`. Two refs means `<ref-a>..<ref-b>`.

### Flow

1. Parse args into ref_a and ref_b (default ref_b = HEAD / current working dir)
2. Create a temporary git worktree for ref_a
3. Run `callgraph build` on the worktree directory
4. Run `callgraph build` on current working dir (skip if `.callgraph/` is fresh)
5. Load both `nodes.json` + `edges.json`
6. Call `compute_diff(graph_a, graph_b, meta={source:'commits', ref_a, ref_b})`
7. Write `.callgraph/diff.json`
8. Clean up worktree
9. Print summary: added/removed/modified/moved counts

### Edge Cases

- `.callgraph/` exists and is recent: skip rebuild for current dir
- Worktree creation fails (ref not found): report error
- No structural changes detected: report "no diff" clearly

### Implementation

This is a mechanical workflow — the skill instructs Claude to run bash commands:
- `git worktree add /tmp/prism-diff-XXXX <ref>`
- `callgraph build /tmp/prism-diff-XXXX -o /tmp/prism-diff-XXXX/.callgraph`
- `callgraph build . -o .callgraph`
- Python script to load both graphs, compute_diff, write diff.json
- `git worktree remove /tmp/prism-diff-XXXX`

## Skill 2: `/impact`

### Trigger
```
/impact docs/plans/add-payment-gateway.md
/impact                  # prompts for file
```

### Flow

1. Read the spec/plan document
2. Claude analyzes it, extracting:
   - "Files affected" / "Changes" sections (often already present)
   - New services/modules to add
   - Things to remove or refactor
   - Dependencies between new and existing components
3. Load `.callgraph/nodes.json` to know what currently exists
4. Map findings to plan operations:
   - `add` ops for new files/services with `depends_on` links
   - `remove` ops for deletions
   - `move` ops for refactors
   - Modify `lines_of_code` estimates based on spec scope
5. Run `apply_plan(current_graph, plan)` — cascading diff
6. Write `.callgraph/diff.json` (meta.source='plan', meta.plan_name)
7. Write `.callgraph/plan.json` for inspection
8. Print impact summary

### Plan JSON Format

Already defined in `plan_engine.py`:

```json
{
  "name": "Add Payment Gateway",
  "description": "Replace billing with payment gateway",
  "operations": [
    {"op": "add", "name": "payment_handler.py", "layer": "C3", "depends_on": ["dir:auth-service"]},
    {"op": "remove", "id": "dir:billing-service"},
    {"op": "move", "id": "file:shared/auth.py", "to_layer": "C2"}
  ]
}
```

### Claude Intelligence Required

- Mapping spec prose to graph operations (e.g. "Add rate limiter to auth-service" → add op)
- Matching "files affected" lists to existing graph node IDs
- Estimating LOC delta from scope descriptions
- Understanding that removing a service implies removing its children (cascading handled by diff engine)

## Architecture Decisions

- **Git worktrees** for `/diff` — doesn't touch working directory, fast, clean
- **Two separate skills** — fundamentally different workflows (mechanical vs intelligent)
- **No auto-open viewer** — just produce diff.json, user opens viewer when ready
- **Cascading handled by engine** — skills don't need to compute transitive effects
- **Skill files are markdown** — Claude Code skills that guide Claude through the steps

## Dependencies

- `callgraph build` CLI must work
- `graph_diff.compute_diff` and `plan_engine.apply_plan` must be importable
- Git must be available for worktree operations
- `.callgraph/` must exist (or `/diff` rebuilds it)

## File Locations

```
.claude/
  commands/
    diff.md          # /diff skill
    impact.md        # /impact skill
```
