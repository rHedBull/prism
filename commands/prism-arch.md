---
description: "Review and maintain the semantic C4 architecture configuration"
---

# /prism-arch — Architecture Config Management

Automatically review and correct `.callgraph/architecture.yaml` — the semantic C4 classification for this codebase.

## Steps

1. **Ensure config exists.** If `.callgraph/architecture.yaml` is missing, run:
   ```bash
   callgraph build .
   ```

2. **Read the config** and the codebase structure:
   ```bash
   cat .callgraph/architecture.yaml
   ```

3. **Review every `confirmed: false` entry.** For each one, apply the decision tree top-down:

   **Is it a System?** (Different product goal, different user base)
   → Move to `systems` section, remove from `containers`.

   **Is it a Container?** Apply the 2-of-6 rule — does it meet **2 or more**:
   - Runs as its own process / service
   - Has its own deploy pipeline
   - Scales independently
   - Different tech stack from siblings
   - Separate runtime responsibility
   - Needs its own monitoring

   → If yes: set `confirmed: true`.
   → If no: it's not a real container. Remove it from `containers` and add to `overrides` with level 1 (component).

   **Quick gut check:** Would Kubernetes deploy it separately? If not, it's not a C2.

4. **Check for missing containers.** Scan top-level dirs not in the config. A dir without a Dockerfile can still be a container if it meets 2-of-6.

5. **Check for systems.** If the repo has multiple independent products, group their containers under `systems` entries.

6. **Write the corrected config** to `.callgraph/architecture.yaml`.

7. **Rebuild and verify:**
   ```bash
   callgraph build .
   ```
   Then print the directory classification summary:
   ```bash
   python3 -c "
   import json
   nodes = json.loads(open('.callgraph/nodes.json').read())
   dirs = [n for n in nodes if n['type'] == 'directory']
   for d in sorted(dirs, key=lambda x: x['file_path']):
       level = d['abstraction_level']
       label = {3: 'SYSTEM', 2: 'CONTAINER', 1: 'COMPONENT'}.get(level, f'L{level}')
       print(f'  [{label:>9}]  {d[\"file_path\"]}')
   "
   ```

8. **Report** what was changed and why, referencing which criteria each entry met or failed.

## Decision Tree

```
Different product goal?          → System  (level 3)
Separate deploy/runtime? (2/6)   → Container (level 2)
Clear replaceable module?        → Component (level 1)
Otherwise                        → Code (level 0, auto-assigned)
```

## Container 2-of-6 Criteria

A directory is a container if **2 or more** of these are true:

1. Runs as its own process / service
2. Has its own deploy pipeline
3. Scales independently
4. Different tech stack from siblings
5. Separate runtime responsibility
6. Needs its own monitoring

**Examples:** API backend, agent scheduler, mobile app, database, message queue, frontend SPA
**Not containers:** helper modules, shared utils, internal libraries — these are components.

## Component Criteria

A directory is a component if:

- Has a clear, single responsibility
- Can be replaced without changing the container's external API
- Has a clear interface (imports/exports boundary)
- Owned by one team or logical module

**Examples:** planner, reward model, auth routes, billing integration, data models

## Config Schema

```yaml
version: 1
systems:
  - path: "platform"
    name: "Core Platform"
containers:
  - path: "platform/api-backend"
    name: "API Backend"
    detected_by: "Dockerfile"
    confirmed: true
  - path: "platform/mobile-app"
    name: "Mobile App"
    detected_by: null                    # manually added, no file signal
    confirmed: true
overrides:
  "shared-utils": 1    # force to component — it's a helper, not a service
```

## Common Mistakes

- **Every micro-feature becomes a service** → too many C2s. A module is a C3.
- **Huge monolith with no modules** → missing C3s. Look for replaceable boundaries.
- **Using repos to define containers** → wrong abstraction. Repo != runtime.
- **Dockerfile = container** → not always. A Dockerfile for a build tool isn't a runtime unit.
- **entrypoint = container** → a `main.py` in a shared library doesn't make it a service.
