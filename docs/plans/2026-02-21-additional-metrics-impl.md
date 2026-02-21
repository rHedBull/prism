# Additional Metrics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 6 new metrics (instability, coupling, type, cyclomatic_complexity, param_count, max_nesting) to the viewer dropdowns and upgrade the "complexity" default to use cyclomatic_complexity for C4 functions.

**Architecture:** Two layers of changes. The parser layer adds 3 new AST-extracted fields (cyclomatic_complexity, param_count, max_nesting) to function/class nodes in both Python and TypeScript parsers. The viewer layer adds 3 derived metrics (instability, coupling, type) in metrics.js computed at load time, updates the complexity default, and adds all 6 new options to the HTML dropdowns.

**Tech Stack:** Python (tree-sitter), JavaScript (Three.js), HTML

---

### Task 1: Add AST metric helpers to Python parser

**Files:**
- Modify: `src/callgraph/parsers/python_parser.py`

**Step 1: Add the three helper functions after `_extract_calls`**

Add these three functions at the end of `python_parser.py`, after the `_extract_imports` function:

```python
def _cyclomatic_complexity(node):
    """Count decision points in an AST subtree. Base complexity = 1."""
    DECISION_TYPES = {
        "if_statement", "elif_clause", "for_statement", "while_statement",
        "try_statement", "except_clause", "conditional_expression",
    }
    count = 1
    def _walk(n):
        nonlocal count
        if n.type in DECISION_TYPES:
            count += 1
        if n.type == "boolean_operator":
            # each `and`/`or` adds a path
            count += 1
        for child in n.children:
            _walk(child)
    _walk(node)
    return count


def _param_count(node):
    """Count parameters in a function_definition node."""
    params = node.child_by_field_name("parameters")
    if not params:
        return 0
    count = 0
    for child in params.children:
        if child.type in ("identifier", "default_parameter", "typed_parameter",
                          "typed_default_parameter", "list_splat_pattern",
                          "dictionary_splat_pattern"):
            count += 1
    return count


def _max_nesting(node, depth=0):
    """Compute maximum nesting depth of control structures."""
    NESTING_TYPES = {
        "if_statement", "for_statement", "while_statement",
        "with_statement", "try_statement", "function_definition",
    }
    max_depth = depth
    for child in node.children:
        child_depth = depth + 1 if child.type in NESTING_TYPES else depth
        max_depth = max(max_depth, _max_nesting(child, child_depth))
    return max_depth
```

**Step 2: Attach metrics to function nodes**

In `_extract_nodes`, in the `if node.type == "function_definition":` block, add the three new fields to the dict appended to `result`. Replace:

```python
            result.append({
                "id": f"func:{file_path}:{name}",
                "type": "function",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "calls": calls,
            })
```

With:

```python
            result.append({
                "id": f"func:{file_path}:{name}",
                "type": "function",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "calls": calls,
                "cyclomatic_complexity": _cyclomatic_complexity(body) if body else 1,
                "param_count": _param_count(node),
                "max_nesting": _max_nesting(body) if body else 0,
            })
```

**Step 3: Attach metrics to class nodes**

In the `if node.type == "class_definition":` block, add the three fields with sensible defaults. Replace:

```python
            result.append({
                "id": f"class:{file_path}:{name}",
                "type": "class",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
            })
```

With:

```python
            body = node.child_by_field_name("body")
            result.append({
                "id": f"class:{file_path}:{name}",
                "type": "class",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "cyclomatic_complexity": _cyclomatic_complexity(body) if body else 1,
                "param_count": 0,
                "max_nesting": _max_nesting(body) if body else 0,
            })
```

**Step 4: Commit**

```bash
git add src/callgraph/parsers/python_parser.py
git commit -m "feat: extract cyclomatic complexity, param count, nesting depth from Python AST"
```

---

### Task 2: Add AST metric helpers to TypeScript parser

**Files:**
- Modify: `src/callgraph/parsers/typescript_parser.py`

**Step 1: Add the three helper functions at the end of the file**

Add after the `_extract_imports` function:

```python
def _cyclomatic_complexity(node):
    """Count decision points in an AST subtree. Base complexity = 1."""
    DECISION_TYPES = {
        "if_statement", "switch_case", "for_statement", "for_in_statement",
        "while_statement", "do_statement", "catch_clause", "ternary_expression",
    }
    count = 1
    def _walk(n):
        nonlocal count
        if n.type in DECISION_TYPES:
            count += 1
        if n.type == "binary_expression":
            op = n.child_by_field_name("operator")
            if op:
                op_text = op.type if hasattr(op, 'type') else ''
                # tree-sitter stores operator as raw text in the node
                raw = n.text[n.children[1].start_byte - n.start_byte:n.children[1].end_byte - n.start_byte] if len(n.children) > 1 else b''
                if raw in (b'&&', b'||'):
                    count += 1
        for child in n.children:
            _walk(child)
    _walk(node)
    return count


def _param_count(node):
    """Count parameters of a function/arrow function node."""
    params = node.child_by_field_name("parameters")
    if not params:
        # Arrow functions: check for formal_parameters
        for child in node.children:
            if child.type == "formal_parameters":
                params = child
                break
    if not params:
        return 0
    count = 0
    for child in params.children:
        if child.type in ("required_parameter", "optional_parameter",
                          "rest_parameter", "identifier", "assignment_pattern"):
            count += 1
    return count


def _max_nesting(node, depth=0):
    """Compute maximum nesting depth of control structures."""
    NESTING_TYPES = {
        "if_statement", "for_statement", "for_in_statement",
        "while_statement", "do_statement", "try_statement",
        "switch_statement", "arrow_function", "function_declaration",
    }
    max_depth = depth
    for child in node.children:
        child_depth = depth + 1 if child.type in NESTING_TYPES else depth
        max_depth = max(max_depth, _max_nesting(child, child_depth))
    return max_depth
```

**Step 2: Attach metrics in `_add_function_node`**

In `_add_function_node`, add the three fields. The `body_node` is already available (either passed in or fetched via `child_by_field_name("body")`). Replace the `result.append` block:

```python
    result.append({
        "id": f"func:{file_path}:{name}",
        "type": "function",
        "name": name,
        "file_path": file_path,
        "lines_of_code": loc,
        "start_line": scope_node.start_point[0] + 1,
        "end_line": scope_node.end_point[0] + 1,
        "calls": calls,
    })
```

With:

```python
    # For param_count, use body_node (arrow fn) or scope_node (function decl)
    param_source = body_node if body_node and body_node.type == "arrow_function" else scope_node
    result.append({
        "id": f"func:{file_path}:{name}",
        "type": "function",
        "name": name,
        "file_path": file_path,
        "lines_of_code": loc,
        "start_line": scope_node.start_point[0] + 1,
        "end_line": scope_node.end_point[0] + 1,
        "calls": calls,
        "cyclomatic_complexity": _cyclomatic_complexity(body_node) if body_node else 1,
        "param_count": _param_count(param_source),
        "max_nesting": _max_nesting(body_node) if body_node else 0,
    })
```

**Step 3: Attach metrics to class/interface/type nodes**

There are three places in `_extract_nodes` that append class nodes (inside `export_statement`, standalone `interface_declaration`/`type_alias_declaration`, and `class_declaration`). For each, add the three fields with `cyclomatic_complexity: 1, param_count: 0, max_nesting: 0`.

For example, replace each class result.append like:

```python
                    result.append({
                        "id": f"class:{file_path}:{name}",
                        "type": "class",
                        "name": name,
                        "file_path": file_path,
                        "lines_of_code": loc,
                        "start_line": child.start_point[0] + 1,
                        "end_line": child.end_point[0] + 1,
                    })
```

With:

```python
                    result.append({
                        "id": f"class:{file_path}:{name}",
                        "type": "class",
                        "name": name,
                        "file_path": file_path,
                        "lines_of_code": loc,
                        "start_line": child.start_point[0] + 1,
                        "end_line": child.end_point[0] + 1,
                        "cyclomatic_complexity": 1,
                        "param_count": 0,
                        "max_nesting": 0,
                    })
```

Do this for all three class/interface append sites (lines ~83-91, ~99-107, ~115-123 in the current file).

**Step 4: Commit**

```bash
git add src/callgraph/parsers/typescript_parser.py
git commit -m "feat: extract cyclomatic complexity, param count, nesting depth from TypeScript AST"
```

---

### Task 3: Add derived metrics and new options to the viewer

**Files:**
- Modify: `web/js/metrics.js`
- Modify: `web/index.html`

**Step 1: Update metrics.js — add derived metrics, type colors, complexity default**

In `metrics.js`, update `SIZE_METRICS` and `COLOR_METRICS`:

```javascript
export const SIZE_METRICS = ['complexity', 'lines_of_code', 'export_count', 'fan_in', 'fan_out', 'child_count', 'cyclomatic_complexity', 'param_count', 'max_nesting', 'instability', 'coupling'];
export const COLOR_METRICS = ['language', 'type', 'lines_of_code', 'export_count', 'fan_in', 'fan_out', 'child_count', 'cyclomatic_complexity', 'param_count', 'max_nesting', 'instability', 'coupling'];
```

Add `TYPE_COLORS` after `LANGUAGE_COLORS`:

```javascript
const TYPE_COLORS = {
    function: 0x4A90D9,   // blue
    class: 0x8c60f3,      // purple
    component: 0x2ECC71,  // green
    container: 0xE67E22,  // orange
    system: 0xE74C3C,     // red
};
```

Update `resolveSizeMetric` to use `cyclomatic_complexity` for C4:

```javascript
function resolveSizeMetric(node) {
    if (_sizeMetric !== 'complexity') return _sizeMetric;
    const level = node.abstraction_level ?? 0;
    return level === 0 ? 'cyclomatic_complexity' : 'child_count';
}
```

In `computeDerivedMetrics`, after attaching fan_in/fan_out/child_count, add instability and coupling:

```javascript
    // Attach to nodes
    for (const node of nodes) {
        node.fan_in = fanIn[node.id] || 0;
        node.fan_out = fanOut[node.id] || 0;
        node.child_count = childCount[node.id] || 0;
        const total = node.fan_in + node.fan_out;
        node.coupling = total;
        node.instability = total > 0 ? +(node.fan_out / total).toFixed(2) : 0;
    }
```

In `computeColor`, add `type` as categorical (after the `language` check):

```javascript
export function computeColor(node, metricRange) {
    if (_colorMetric === 'language') {
        return LANGUAGE_COLORS[node.language] || 0x888888;
    }
    if (_colorMetric === 'type') {
        return TYPE_COLORS[node.type] || 0x888888;
    }
    // ... rest unchanged
```

In `computeMetricRange`, handle `type` as categorical:

```javascript
export function computeMetricRange(allNodes) {
    if (_colorMetric === 'language' || _colorMetric === 'type') return { min: 0, max: 1 };
    // ... rest unchanged
```

**Step 2: Update index.html dropdowns**

Replace the `#metric-size` select options with:

```html
                    <select id="metric-size">
                        <option value="complexity" selected>Complexity</option>
                        <option value="lines_of_code">Lines of Code</option>
                        <option value="cyclomatic_complexity">Cyclomatic Complexity</option>
                        <option value="param_count">Param Count</option>
                        <option value="max_nesting">Max Nesting</option>
                        <option value="export_count">Export Count</option>
                        <option value="fan_in">Fan In</option>
                        <option value="fan_out">Fan Out</option>
                        <option value="coupling">Coupling</option>
                        <option value="instability">Instability</option>
                        <option value="child_count">Child Count</option>
                    </select>
```

Replace the `#metric-color` select options with:

```html
                    <select id="metric-color">
                        <option value="language" selected>Language</option>
                        <option value="type">Node Type</option>
                        <option value="lines_of_code">Lines of Code</option>
                        <option value="cyclomatic_complexity">Cyclomatic Complexity</option>
                        <option value="param_count">Param Count</option>
                        <option value="max_nesting">Max Nesting</option>
                        <option value="export_count">Export Count</option>
                        <option value="fan_in">Fan In</option>
                        <option value="fan_out">Fan Out</option>
                        <option value="coupling">Coupling</option>
                        <option value="instability">Instability</option>
                        <option value="child_count">Child Count</option>
                    </select>
```

**Step 3: Commit**

```bash
git add web/js/metrics.js web/index.html
git commit -m "feat: add 6 new metrics to viewer dropdowns with cyclomatic complexity default"
```

---

### Task 4: Rebuild callgraph data and verify

**Step 1: Rebuild the callgraph for the test project**

```bash
callgraph build test-project/
```

Verify the new fields appear in nodes.json:

```bash
python3 -c "import json; nodes=json.load(open('.callgraph/nodes.json')); func=[n for n in nodes if n['type']=='function'][0]; print(func.get('cyclomatic_complexity'), func.get('param_count'), func.get('max_nesting'))"
```

Expected: three numeric values (not None).

**Step 2: Visual smoke test**

Run `callgraph serve`, open browser and verify:
1. Default "Complexity" — C4 blocks now sized by cyclomatic_complexity (not LOC)
2. Size dropdown: "Cyclomatic Complexity", "Param Count", "Max Nesting", "Coupling", "Instability" all resize blocks
3. Color dropdown: "Node Type" shows categorical colors (blue functions, purple classes, green components, orange containers, red system)
4. Color dropdown: numeric metrics show blue-to-red gradient
5. Info panel label updates correctly for each metric
6. Hover highlighting still works
7. Visibility toggles still trigger relative recalculation

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: address issues from integration testing"
```

**Step 4: Push**

```bash
git push
```
