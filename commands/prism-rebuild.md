---
description: "Rebuild callgraph, generate semantic data, and restart the visualization server"
---
# /rebuild — Rebuild & Serve

Rebuild the callgraph data, enrich with semantic labels, and restart the dev server.

## Steps

1. **Build the graph:**
   ```bash
   callgraph build . -o .callgraph
   ```

2. **Enrich with semantic labels.** Read the built graph and generate `.callgraph/semantic.json`:

   Read `.callgraph/nodes.json` and `.callgraph/edges.json`. List all C3 (abstraction_level === 1) and C2 (abstraction_level === 2) components with their children.

   For each meaningful pair of C3/C2 components:
   - Look at the component names and the function/class names of their children
   - Infer the conceptual relationship between them
   - Generate a 2-4 word verb phrase describing the relationship (e.g. "delegates parsing to", "serves data to", "validates")
   - Assign each C3/C2 node a category from this fixed set: `api`, `auth`, `database`, `ui`, `config`, `util`, `core`, `test`, `model`, `service`

   Optionally run this Python snippet first to see aggregated cross-component edges (if any exist):
   ```bash
   python3 -c "
   import json
   nodes = json.load(open('.callgraph/nodes.json'))
   edges = json.load(open('.callgraph/edges.json'))
   by_id = {n['id']: n for n in nodes}
   def ancestor(nid, target_levels):
       visited = set()
       cur = nid
       while cur and cur not in visited:
           node = by_id.get(cur)
           if not node: break
           if node.get('abstraction_level') in target_levels: return cur
           visited.add(cur)
           cur = node.get('parent')
       return None
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
   for (a, b), types in sorted(pairs.items(), key=lambda x: -sum(x[1].values())):
       print(f'{a} -> {b}: {dict(types)}')
   "
   ```

   Even if no cross-component edges are found, you MUST still generate semantic.json by inferring relationships from component names and structure. The semantic edges are conceptual — they describe how components relate architecturally, not just code-level calls.

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

3. **Kill any running server:**
   ```bash
   pkill -f "python serve.py" || true
   ```

4. **Start the server:**
   ```bash
   python serve.py &
   ```
   Wait for it to be ready (check `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080` returns 200).

5. **Report results.** Print the build summary (node/edge counts), number of semantic edges and categories, and confirm the server is running at http://localhost:8080.
