from pathlib import Path
from callgraph.discovery import discover_files

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_discovers_python_files():
    files = discover_files(TEST_PROJECT)
    py_files = [f for f in files if f["language"] == "python"]
    assert len(py_files) == 16
    paths = {f["path"] for f in py_files}
    assert "backend/services/auth_service.py" in paths

def test_discovers_typescript_files():
    files = discover_files(TEST_PROJECT)
    ts_files = [f for f in files if f["language"] in ("typescript", "typescriptreact")]
    assert len(ts_files) >= 10
    paths = {f["path"] for f in ts_files}
    assert "frontend/src/App.tsx" in paths

def test_skips_non_source_files():
    files = discover_files(TEST_PROJECT)
    extensions = {Path(f["path"]).suffix for f in files}
    assert ".md" not in extensions
    assert ".json" not in extensions
    assert ".toml" not in extensions
    assert ".html" not in extensions

def test_file_entry_has_required_fields():
    files = discover_files(TEST_PROJECT)
    for f in files:
        assert "path" in f
        assert "absolute_path" in f
        assert "language" in f
