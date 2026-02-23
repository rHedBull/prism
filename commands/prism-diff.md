---
description: "Compare callgraph structure between git refs and write diff.json for the viewer"
argument-hint: "<git-ref or ref-a..ref-b>"
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

7. **Enrich with semantic labels.** Read the built graph and generate `.callgraph/semantic.json`:

   Read `.callgraph/nodes.json` and `.callgraph/edges.json`. For each pair of C3 components (abstraction_level === 1) or C2 containers (abstraction_level === 2) that have edges between their children:

   - Count the underlying edges by type (calls, imports, inherits_from, depends_on)
   - Look at the function/class names involved on each side
   - Generate a 2-4 word verb phrase describing the relationship (e.g. "authenticates against", "reads data from", "orchestrates")
   - Assign each C3/C2 node a category from this fixed set: `api`, `auth`, `database`, `ui`, `config`, `util`, `core`, `test`, `model`, `service`

   Write the result as `.callgraph/semantic.json`:
   ```json
   {
     "edges": [
       {"from": "dir:src/auth", "to": "dir:src/db", "label": "validates against", "weight": 10, "types": {"calls": 8, "imports": 2}}
     ],
     "node_categories": {
       "dir:src/auth": "auth",
       "dir:src/db": "database"
     }
   }
   ```

   Use a Python snippet to aggregate the edge pairs:
   ```bash
   python3 -c "
   import json
   nodes = json.load(open('.callgraph/nodes.json'))
   edges = json.load(open('.callgraph/edges.json'))

   # Build parent chain: node -> nearest C3/C2 ancestor
   by_id = {n['id']: n for n in nodes}
   def ancestor(nid, target_levels):
       visited = set()
       cur = nid
       while cur and cur not in visited:
           node = by_id.get(cur)
           if not node: break
           if node.get('abstraction_level') in target_levels:
               return cur
           visited.add(cur)
           cur = node.get('parent')
       return None

   # Aggregate edges between C3 pairs
   pairs = {}
   for e in edges:
       if e['type'] == 'contains': continue
       a = ancestor(e['from'], {1, 2})
       b = ancestor(e['to'], {1, 2})
       if not a or not b or a == b: continue
       key = (a, b)
       if key not in pairs: pairs[key] = {}
       t = e['type']
       pairs[key][t] = pairs[key].get(t, 0) + 1

   result = []
   for (a, b), types in pairs.items():
       weight = sum(types.values())
       result.append({'from': a, 'to': b, 'weight': weight, 'types': types})

   print(json.dumps(result, indent=2))
   "
   ```

   Use the aggregated pairs output to generate semantic labels. For each pair, based on the component names, edge types, and weights, write a 2-4 word verb phrase as the `label`. Also assign each unique node ID a category. Write the complete `semantic.json`.

8. **Report results.** Print the diff summary. Tell the user:
   - `diff.json` has been written to `.callgraph/diff.json`
   - Run `callgraph serve` or reload the viewer to see the visual diff

## Error Handling

- If the ref doesn't exist, report the error and suggest `git branch -a` to list available refs.
- If `callgraph build` fails, report which path failed.
- Always clean up the worktree, even on error.
