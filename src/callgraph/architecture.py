"""Semantic C4 architecture detection and configuration."""

import re
from pathlib import Path

import yaml


# Files/patterns that signal a directory is a runtime container
_CONTAINER_SIGNALS = {
    "Dockerfile": "Dockerfile",
    "docker-compose.yml": "docker-compose.yml",
    "docker-compose.yaml": "docker-compose.yaml",
    "go.mod": "go.mod",
}

_ENTRYPOINT_FILES = {
    "main.py", "app.py", "server.py",
    "index.js", "server.js", "main.js",
    "index.ts", "server.ts", "main.ts",
}


def detect_containers(root: Path) -> list[dict]:
    """Walk repo and detect directories that look like runtime containers."""
    root = Path(root).resolve()
    containers = []
    seen = set()

    for dirpath in sorted(root.rglob("*")):
        if not dirpath.is_dir():
            continue
        rel = dirpath.relative_to(root)
        rel_str = str(rel)

        # Skip hidden dirs and common non-source dirs
        if any(p.startswith(".") for p in rel.parts):
            continue
        if any(p in ("node_modules", "__pycache__", "venv", ".venv", "build", "dist")
               for p in rel.parts):
            continue

        signal = _detect_signal(dirpath)
        if signal and rel_str not in seen:
            seen.add(rel_str)
            containers.append({
                "path": rel_str,
                "name": rel.name,
                "detected_by": signal,
            })

    return containers


def _detect_signal(dirpath: Path) -> str | None:
    """Check a directory for container signals. Returns description or None."""
    # Static file signals
    for filename, label in _CONTAINER_SIGNALS.items():
        if (dirpath / filename).is_file():
            return label

    # package.json with start/dev script or main field
    pkg = dirpath / "package.json"
    if pkg.is_file():
        try:
            import json
            data = json.loads(pkg.read_text())
            scripts = data.get("scripts", {})
            if any(k in scripts for k in ("start", "dev", "serve")):
                return "package.json:scripts"
            if "main" in data:
                return "package.json:main"
        except (json.JSONDecodeError, OSError):
            pass

    # pyproject.toml with [project.scripts]
    pyproject = dirpath / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text()
            if "[project.scripts]" in text:
                return "pyproject.toml:project.scripts"
        except OSError:
            pass

    # Cargo.toml with [[bin]]
    cargo = dirpath / "Cargo.toml"
    if cargo.is_file():
        try:
            text = cargo.read_text()
            if "[[bin]]" in text:
                return "Cargo.toml:bin"
        except OSError:
            pass

    # Makefile with run/serve/start targets
    makefile = dirpath / "Makefile"
    if makefile.is_file():
        try:
            text = makefile.read_text()
            if re.search(r"^(run|serve|start)\s*:", text, re.MULTILINE):
                return "Makefile:run/serve/start"
        except OSError:
            pass

    # Entrypoint files
    for entry in _ENTRYPOINT_FILES:
        if (dirpath / entry).is_file():
            return f"entrypoint:{entry}"

    return None


def load_architecture_config(output_dir: str | Path) -> dict | None:
    """Read existing architecture.yaml from output directory."""
    path = Path(output_dir) / "architecture.yaml"
    if not path.is_file():
        return None
    try:
        return yaml.safe_load(path.read_text()) or {}
    except (yaml.YAMLError, OSError):
        return None


def merge_architecture_config(existing: dict | None, detected: list[dict]) -> dict:
    """Merge detected containers with existing config, preserving manual edits.

    New auto-detections get confirmed: false. Existing entries (including
    agent-confirmed ones and manually added containers) are preserved as-is.
    """
    if existing is None:
        for det in detected:
            det["confirmed"] = False
        return {
            "version": 1,
            "systems": [],
            "containers": detected,
            "overrides": {},
        }

    existing_paths = {c["path"] for c in existing.get("containers", [])}
    merged_containers = list(existing.get("containers", []))

    # Add newly detected containers not already in config
    for det in detected:
        if det["path"] not in existing_paths:
            det["confirmed"] = False
            merged_containers.append(det)

    return {
        "version": existing.get("version", 1),
        "systems": existing.get("systems", []),
        "containers": merged_containers,
        "overrides": existing.get("overrides", {}),
    }


def write_architecture_config(config: dict, output_dir: str | Path):
    """Write architecture.yaml to output directory."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "architecture.yaml"
    path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))


def build_level_map(config: dict) -> dict[str, int]:
    """Build path -> abstraction level mapping from architecture config.

    System paths get level 3, container paths get level 2,
    overrides get their specified level.
    """
    level_map = {}

    for system in config.get("systems", []):
        level_map[system["path"]] = 3

    for container in config.get("containers", []):
        level_map[container["path"]] = 2

    # Overrides take precedence
    for path, level in config.get("overrides", {}).items():
        level_map[path] = level

    return level_map
