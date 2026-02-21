# Prism

3D architecture visualizer for codebases. Builds a call graph from source code and renders it as an interactive layered view in the browser.

## Features

- **Graph builder** — static analysis of Python and TypeScript/JS codebases using tree-sitter
- **C4-style layers** — nodes organized by abstraction level (system, service, component, code)
- **3D viewer** — Three.js scene with force-directed layout, hover inspection, edge highlighting
- **Diff engine** — compare graph structure between git refs or planned changes
- **Claude Code plugin** — `/prism-diff` and `/prism-impact` commands

## Install

```bash
pip install -e .
```

## Usage

```bash
# Build the call graph
callgraph build <path-to-repo> -o .callgraph

# Start the 3D viewer
callgraph serve

# Compare two graph snapshots
callgraph diff <dir-a> <dir-b> -o .callgraph --ref-a main --ref-b HEAD

# Apply an architectural plan
callgraph plan plan.json --graph-dir . -o .callgraph
```

## Claude Code Plugin

Install as a plugin to get `/prism-diff` and `/prism-impact` commands:

```bash
claude plugin marketplace add rHedBull/prism
claude plugin install prism
```

- `/prism-diff <ref>` — compare callgraph between git refs
- `/prism-impact <spec.md>` — visualize structural impact of a planned change

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
