---
description: "Review and maintain the semantic C4 architecture configuration"
---

# /prism-arch — Architecture Config Management

Review, validate, and update `.callgraph/architecture.yaml` — the semantic C4 classification for this codebase.

## Decision Tree

Classify top-down. Ask in order for each directory:

1. **Different product goal?** → System (level 3)
2. **Separate deploy/runtime?** → Container (level 2)
3. **Clear replaceable module?** → Component (level 1)
4. **Otherwise** → Code (level 0, auto-assigned)

## C4 Level Definitions

| Level | C4 Term   | What it means | Decision heuristic |
|-------|-----------|---------------|-------------------|
| 3 | System | Product boundary | Different product goal, different user base |
| 2 | Container | Deployable runtime unit | Would Kubernetes deploy it separately? |
| 1 | Component | Replaceable module inside a container | Could you rewrite it without touching the rest? |
| 0 | Code | Classes/functions | Auto-assigned, not configured |

### Detecting a Container (C2)

A directory is a container if **2 or more** of these are true:

- Runs as its own process / service
- Has its own deploy pipeline
- Scales independently
- Different tech stack from siblings
- Separate runtime responsibility
- Needs its own monitoring

**Examples:** API backend, agent scheduler, mobile app, database, message queue, frontend SPA

**Not containers:** helper modules, shared utils, internal libraries — these are components.

The auto-detector looks for file signals (Dockerfile, entrypoints, package.json scripts) as a starting hint. But a container without a Dockerfile is still a container if it meets the criteria above. **Review every auto-detection against the 2-of-6 rule.**

### Detecting a Component (C3)

A directory is a component if:

- Has a clear, single responsibility
- Can be replaced without changing the container's external API
- Has a clear interface (imports/exports boundary)
- Owned by one team or logical module

**Examples inside a container:** planner, reward model, auth module, billing integration, API routes

### Detecting a System (C1)

A system = product boundary. Defined by the agent, not auto-detected.

- **Monorepo with multiple products:** each product is a system
- **Platform + supporting services:** platform is one system, monitoring/tooling is another
- **Single product:** omit `systems` entirely (a synthetic root is created)

## Steps

1. **Check current config:**
   ```bash
   cat .callgraph/architecture.yaml 2>/dev/null || echo "No config found"
   ```
   If missing, run `callgraph build .` first to get auto-detected hints.

2. **Start at the top — define systems** if the repo has multiple products.

3. **Review each container.** For each auto-detected entry:
   - Does it meet 2+ of the container criteria? Keep it.
   - Is it really just a module with an entrypoint? Demote to component via overrides.
   - Are there containers the detector missed? Add them manually.
   - Mark reviewed entries with `confirmed: true`.

4. **Review components.** Components are inferred (dirs inside containers), but check:
   - Are there dirs that should be components but sit outside a container? Use overrides.
   - Are there dirs inside a container that are really sub-containers? Promote them.

5. **Review overrides** for any manual level assignments.

6. **Write corrections** to `.callgraph/architecture.yaml`.

7. **Rebuild:**
   ```bash
   callgraph build .
   ```

## Config Schema

```yaml
version: 1
systems:
  - path: "platform"
    name: "Core Platform"
containers:
  - path: "platform/api-backend"
    name: "API Backend"
    detected_by: "Dockerfile"           # auto-detection signal
    confirmed: true                      # agent reviewed this
  - path: "platform/mobile-app"
    name: "Mobile App"
    detected_by: null                    # manually added, no file signal
    confirmed: true
overrides:
  "shared-utils": 1    # force to component (C3) — it's a helper, not a service
```

## Common Mistakes

- **Every micro-feature becomes a service** → too many C2s. A module is a C3.
- **Huge monolith with no modules** → missing C3s. Look for replaceable boundaries.
- **Using repos to define containers** → wrong abstraction. Repo != runtime.
- **Dockerfile = container** → not always. A Dockerfile for a build tool isn't a runtime unit.

## Tips

- Auto-detection runs on every `callgraph build` — new hints are merged in
- Manual edits (systems, confirmed, manual containers) are preserved across rebuilds
- Use `confirmed: true` to mark entries the agent has reviewed
- Unconfirmed detections should be reviewed before trusting the architecture view
