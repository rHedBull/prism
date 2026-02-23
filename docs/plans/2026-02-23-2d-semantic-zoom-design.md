# 2D Semantic Zoom Viewing Mode

## Summary

Add a 2D viewing mode alongside the existing 3D view. Uses an orthographic top-down camera with a nested treemap layout. Semantic zoom reveals deeper abstraction layers as you zoom in — start seeing only C1, zoom to reveal C2 inside C1 containers, then C3, then C4.

## Approach

**Three.js Orthographic Camera** — reuses existing Three.js infrastructure (renderer, raycasting, interaction, diff overlay) while providing a true 2D feel.

## Mode Toggle

- 2D/3D toggle button in the top toolbar
- **To 2D**: Swap to orthographic camera (top-down, Y-axis), disable orbit rotation, enable pan + scroll-zoom. Build nested treemap at Y=0.
- **To 3D**: Restore perspective camera and OrbitControls. Show original stacked layers.

## Nested Treemap Layout

All nodes in a single XZ plane using nested squarified treemap:

```
+---------------------------+------------------+
| C1: Backend               | C1: Frontend     |
| +-----------+-----------+ | +------+-------+ |
| | C2: API   | C2: Auth  | | |C2:Web|C2:Mobi| |
| | +---+---+ | +---+---+ | | | ...  | ...   | |
| | |C3a|C3b| | |C3c|C3d| | | +------+-------+ |
| | +---+---+ | +---+---+ | |                  |
| +-----------+-----------+ |                  |
+---------------------------+------------------+
```

- C1 boxes outermost, sized by total LOC or child count
- C2 nests inside C1, C3 inside C2, C4 inside C3
- Padding between nesting levels so parent boundaries visible
- Node height (3D) maps to color intensity or border thickness in 2D

## Semantic Zoom Behavior

Zoom level (orthographic frustum size) determines which layers render with detail:

| Zoom Level | Visible Detail | Behavior |
|------------|---------------|----------|
| Far out    | C1 only       | C1 filled boxes with labels |
| Medium-far | C1 + C2       | C1 becomes container (border), C2 boxes appear inside |
| Medium     | C2 + C3       | C1 faint border, C2 container, C3 boxes appear |
| Close      | C3 + C4       | C1/C2 very faint, C3 container, C4 boxes with labels |

Transitions are smooth — deeper boxes fade in (opacity 0->1), parents transition from filled to outline containers.

## Interaction

- **Hover**: Highlight node, dim non-family, show info panel, show edges as 2D curves
- **Selection**: Double-click to persist (same as 3D)
- **Click container**: Smooth zoom-animate into container to reveal children
- **Pan**: Right-click drag or middle-click drag
- **Zoom**: Scroll wheel
- **Edges**: Hidden by default, shown on hover/selection only

## Diff Mode

Same behavior — changed nodes get diff colors, unchanged dim. Floating 3D markers replaced by colored borders/badges.

## New Files

- `web/js/mode-2d.js` — Orthographic camera setup, zoom controls, semantic zoom logic
- `web/js/layout-treemap.js` — Nested squarified treemap layout algorithm

## Modified Files

- `web/js/main.js` — Mode toggle orchestration, init 2D mode
- `web/js/scene.js` — Camera switching, render adjustments
- `web/js/interaction.js` — 2D-aware raycasting and hover
- `web/js/edges.js` — 2D edge rendering (flat curves)
- `web/js/diff-overlay.js` — 2D diff markers
- `web/index.html` — Toggle button UI
- `web/js/config-panel.js` — Hide layer checkboxes in 2D mode
