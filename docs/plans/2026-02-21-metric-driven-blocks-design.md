# Metric-Driven Block Size & Color

**Date:** 2026-02-21
**Status:** Approved

## Goal

Let users control what metric drives block height and block color via dropdowns in the config panel. Currently height is hardcoded to `lines_of_code` and color to `language`.

## Config Panel Additions

Two new dropdown sections in the existing right-side config panel:

- **"Size by"** dropdown: `complexity` (default), `lines_of_code`, `export_count`, `fan_in`, `fan_out`, `child_count`
- **"Color by"** dropdown: `language` (default), `lines_of_code`, `export_count`, `fan_in`, `fan_out`, `child_count`

## Derived Metrics

At graph load time, compute and attach to each node:

- `fan_in` — count of incoming edges targeting this node
- `fan_out` — count of outgoing edges from this node
- `child_count` — count of direct children in the hierarchy

## Size Mapping

**"Complexity" mode** (default) picks the right metric per abstraction level:
- C4 (functions/classes): `lines_of_code` — how big is the function
- C3 (components/leaf dirs): `child_count` — how many files
- C2 (containers/top dirs): `child_count` — how many components
- C1 (system): `child_count` — how many containers

All other options apply a single metric globally. Same log-scale formula:

```
height = Math.max(0.8, Math.log2(Math.max(1, value)) * LOC_SCALE * 8)
```

Only height changes. Width/depth remain hierarchy-driven (subdivideBox).

## Color Mapping

- **`language`** (default): current categorical palette (LANGUAGE_COLORS)
- **Numeric metrics**: sequential gradient, cool-to-warm
  - Low: `0x4A90D9` (blue)
  - High: `0xE74C3C` (red)
  - Values normalized to min/max across visible nodes
  - Linear interpolation in HSL space for smooth transition

## Interaction

- Changing a dropdown triggers in-place material/geometry update (no scene rebuild)
- Info panel on hover shows the active metric value
- Diff mode overrides color mapping when active (existing behavior preserved)
