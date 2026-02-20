from pathlib import Path

EXTENSION_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
}

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "dist", ".callgraph"}

def discover_files(root: Path) -> list[dict]:
    root = Path(root).resolve()
    files = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in EXTENSION_MAP:
            rel = str(path.relative_to(root))
            files.append({
                "path": rel,
                "absolute_path": str(path),
                "language": EXTENSION_MAP[path.suffix],
            })
    return sorted(files, key=lambda f: f["path"])
