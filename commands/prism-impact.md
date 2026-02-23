---
description: "Visualize the structural impact of a planned change from a spec or design document"
argument-hint: "<path-to-spec.md>"
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

   **Layer mapping (semantic C4):**
   - C1 (level 3) = System — product boundary (rare to add)
   - C2 (level 2) = Container — deployable runtime unit (separate process, own deploy pipeline, scales independently)
   - C3 (level 1) = Component — replaceable module inside a container (clear interface, single responsibility)

   **Important:** Match node IDs to existing graph nodes. Node IDs follow the pattern:
   - `dir:<path>` for directories (e.g. `dir:auth-service`, `dir:auth-service/services`)
   - `file:<path>` for files (e.g. `file:auth-service/main.py`)

   Write the plan to `.callgraph/plan.json`.

5. **Apply the plan:**
   ```bash
   callgraph plan .callgraph/plan.json --graph-dir . -o .callgraph
   ```

6. **Enrich with semantic labels.** Read the built graph and generate `.callgraph/semantic.json`:

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

7. **Report results.** Print:
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
