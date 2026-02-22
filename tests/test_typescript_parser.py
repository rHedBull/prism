from pathlib import Path
from callgraph.parsers.typescript_parser import parse_typescript_file

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_extracts_functions_from_tsx():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/components/App.tsx",
        "frontend/src/components/App.tsx"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert len(names) > 0

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

def test_extracts_interfaces():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/types/api.ts",
        "frontend/src/types/api.ts"
    )
    interfaces = [n for n in result["nodes"] if n["type"] == "interface"]
    names = {i["name"] for i in interfaces}
    assert "User" in names
    assert "Workspace" in names

def test_extracts_type_aliases():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/types/api.ts",
        "frontend/src/types/api.ts"
    )
    type_aliases = [n for n in result["nodes"] if n["type"] == "type_alias"]
    names = {t["name"] for t in type_aliases}
    assert "UserRole" in names

def test_class_declaration_stays_class():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/types/api.ts",
        "frontend/src/types/api.ts"
    )
    # Interfaces should not be type "class"
    classes = [n for n in result["nodes"] if n["type"] == "class"]
    interfaces = [n for n in result["nodes"] if n["type"] == "interface"]
    type_aliases = [n for n in result["nodes"] if n["type"] == "type_alias"]
    # This file has interfaces and type aliases but no classes
    assert len(interfaces) > 0
    assert len(type_aliases) > 0
    # All non-function nodes should be interface or type_alias
    non_func = [n for n in result["nodes"] if n["type"] != "function"]
    for n in non_func:
        assert n["type"] in ("interface", "type_alias")

def test_extracts_imports():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/services/auth.ts",
        "frontend/src/services/auth.ts"
    )
    imports = result["imports"]
    sources = {imp["module"] for imp in imports}
    assert len(sources) > 0

def test_node_has_line_count():
    result = parse_typescript_file(
        TEST_PROJECT / "frontend/src/services/auth.ts",
        "frontend/src/services/auth.ts"
    )
    for node in result["nodes"]:
        assert "lines_of_code" in node
        assert node["lines_of_code"] > 0
