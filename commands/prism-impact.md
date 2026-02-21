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
