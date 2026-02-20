from pathlib import Path
from callgraph.parsers.python_parser import parse_python_file

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_extracts_classes():
    result = parse_python_file(
        TEST_PROJECT / "backend/models/user.py",
        "backend/models/user.py"
    )
    classes = [n for n in result["nodes"] if n["type"] == "class"]
    names = {c["name"] for c in classes}
    assert "Base" in names
    assert "User" in names

def test_extracts_functions():
    result = parse_python_file(
        TEST_PROJECT / "backend/services/auth_service.py",
        "backend/services/auth_service.py"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert "hash_password" in names
    assert "verify_password" in names
    assert "create_access_token" in names
    assert "decode_token" in names
    assert "authenticate_user" in names
    assert "register_user" in names

def test_extracts_imports():
    result = parse_python_file(
        TEST_PROJECT / "backend/services/task_service.py",
        "backend/services/task_service.py"
    )
    imports = result["imports"]
    imported_modules = {imp["module"] for imp in imports}
    assert any("backend.models.task" in m for m in imported_modules)
    assert any("backend.services.notification_service" in m for m in imported_modules)

def test_extracts_methods_inside_class():
    result = parse_python_file(
        TEST_PROJECT / "backend/models/user.py",
        "backend/models/user.py"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert "__repr__" in names

def test_node_has_line_count():
    result = parse_python_file(
        TEST_PROJECT / "backend/services/auth_service.py",
        "backend/services/auth_service.py"
    )
    for node in result["nodes"]:
        assert "lines_of_code" in node
        assert node["lines_of_code"] > 0
