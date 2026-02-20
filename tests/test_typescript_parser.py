from pathlib import Path
from callgraph.parsers.typescript_parser import parse_typescript_file

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_extracts_functions_from_tsx():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/App.tsx",
        "frontend/src/App.tsx"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert "App" in names or "ProtectedRoute" in names

def test_extracts_functions_from_ts():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/services/auth.ts",
        "frontend/src/services/auth.ts"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert "login" in names
    assert "register" in names
    assert "logout" in names
    assert "getToken" in names

def test_extracts_interfaces():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/types/api.ts",
        "frontend/src/types/api.ts"
    )
    interfaces = [n for n in result["nodes"] if n["type"] == "class"]
    names = {i["name"] for i in interfaces}
    assert "Task" in names
    assert "User" in names
    assert "LoginRequest" in names

def test_extracts_imports():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/components/TaskList.tsx",
        "frontend/src/components/TaskList.tsx"
    )
    imports = result["imports"]
    sources = {imp["module"] for imp in imports}
    assert any("useTasks" in s for s in sources)
    assert any("TaskCard" in s for s in sources)

def test_node_has_line_count():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/hooks/useTasks.ts",
        "frontend/src/hooks/useTasks.ts"
    )
    for node in result["nodes"]:
        assert "lines_of_code" in node
        assert node["lines_of_code"] > 0
