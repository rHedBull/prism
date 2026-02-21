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
