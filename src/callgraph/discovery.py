from pathlib import Path
import pathspec

EXTENSION_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
}

ALWAYS_SKIP = {".git"}


def _load_gitignore(root: Path) -> pathspec.PathSpec:
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        return pathspec.PathSpec.from_lines("gitwildmatch", gitignore.read_text().splitlines())
    return pathspec.PathSpec.from_lines("gitwildmatch", [])


def discover_files(root: Path) -> list[dict]:
    root = Path(root).resolve()
    spec = _load_gitignore(root)
    files = []
    for path in root.rglob("*"):
        if any(part in ALWAYS_SKIP for part in path.parts):
            continue
        if not path.is_file() or path.suffix not in EXTENSION_MAP:
            continue
        rel = str(path.relative_to(root))
        if spec.match_file(rel):
            continue
        files.append({
            "path": rel,
            "absolute_path": str(path),
            "language": EXTENSION_MAP[path.suffix],
        })
    return sorted(files, key=lambda f: f["path"])
