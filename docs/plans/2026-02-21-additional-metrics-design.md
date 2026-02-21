# Additional Metrics for Block Size & Color

**Date:** 2026-02-21
**Status:** Approved

---

## Goal

Add 6 new metrics to the size/color dropdowns and upgrade the "complexity" default to use actual cyclomatic complexity for C4 functions.

## New Metrics

| Metric | Type | Source | Available on | Size/Color |
|--------|------|--------|-------------|------------|
| instability | derived | `fan_out / (fan_in + fan_out)` | all nodes | both |
| coupling | derived | `fan_in + fan_out` | all nodes | both |
| type | categorical | node.type field | all nodes | color only |
| cyclomatic_complexity | parsed | AST branch counting | functions/classes | both |
| param_count | parsed | AST parameter counting | functions | both |
| max_nesting | parsed | AST depth traversal | functions | both |

## Complexity Default Change

The "complexity" size mode currently maps C4 to `lines_of_code`. After this change it maps C4 to `cyclomatic_complexity`, keeping `child_count` for C3/C2/C1.

## Architecture

### Parser Layer

Both `python_parser.py` and `typescript_parser.py` add 3 new fields to each function/class node:

- `cyclomatic_complexity`: base 1 + count of decision points in the function body
- `param_count`: number of parameters in the function signature
- `max_nesting`: deepest nesting level of control structures

**Cyclomatic complexity node types:**

Python: `if_statement`, `elif_clause`, `for_statement`, `while_statement`, `try_statement`, `except_clause`, `boolean_operator` (and/or), `conditional_expression`

TypeScript: `if_statement`, `switch_case`, `for_statement`, `for_in_statement`, `while_statement`, `do_statement`, `catch_clause`, `ternary_expression`, `binary_expression` with `&&`/`||`

**Nesting depth node types:** same control flow nodes as above (excluding boolean operators and ternary).

### Viewer Layer

`metrics.js` changes:
- `computeDerivedMetrics` computes `instability` and `coupling` from fan_in/fan_out
- `resolveSizeMetric` returns `cyclomatic_complexity` for C4 when mode is "complexity"
- New `TYPE_COLORS` map: function=blue, class=purple, component=green, container=orange, system=red
- `computeColor` handles `type` as categorical (like `language`)

`index.html` changes:
- Add new options to both Size and Color dropdowns
- `type` only in Color dropdown

## Files Changed

- `src/callgraph/parsers/python_parser.py` — add 3 extraction helpers
- `src/callgraph/parsers/typescript_parser.py` — add 3 extraction helpers
- `web/js/metrics.js` — derived metrics, type colors, complexity default
- `web/index.html` — new dropdown options
