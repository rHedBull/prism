from pathlib import Path
from callgraph.parsers.python_parser import parse_python_file

TEST_PROJECT = Path(__file__).parent.parent / "test-project"

def test_extracts_classes():
    result = parse_python_file(
        TEST_PROJECT / "auth-service/services/auth_service.py",
        "auth-service/services/auth_service.py"
    )
    classes = [n for n in result["nodes"] if n["type"] == "class"]
    names = {c["name"] for c in classes}
    assert "AuthService" in names

def test_extracts_functions():
    result = parse_python_file(
        TEST_PROJECT / "gateway/service_registry.py",
        "gateway/service_registry.py"
    )
    functions = [n for n in result["nodes"] if n["type"] == "function"]
    names = {f["name"] for f in functions}
    assert len(names) > 0

def test_extracts_imports():
    result = parse_python_file(
        TEST_PROJECT / "auth-service/services/auth_service.py",
        "auth-service/services/auth_service.py"
    )
    imports = result["imports"]
    imported_modules = {imp["module"] for imp in imports}
    assert any("token_service" in m for m in imported_modules)

def test_node_has_line_count():
    result = parse_python_file(
        TEST_PROJECT / "auth-service/services/auth_service.py",
        "auth-service/services/auth_service.py"
    )
    for node in result["nodes"]:
        assert "lines_of_code" in node
        assert node["lines_of_code"] > 0

def test_class_has_decorators_field():
    result = parse_python_file(
        TEST_PROJECT / "gateway/service_registry.py",
        "gateway/service_registry.py"
    )
    classes = [n for n in result["nodes"] if n["type"] == "class"]
    for c in classes:
        assert "decorators" in c
        assert "bases" in c

def test_dataclass_decorator_extracted():
    result = parse_python_file(
        TEST_PROJECT / "gateway/service_registry.py",
        "gateway/service_registry.py"
    )
    classes = {c["name"]: c for c in result["nodes"] if c["type"] == "class"}
    assert "ServiceInstance" in classes
    assert "dataclass" in classes["ServiceInstance"]["decorators"]

def test_base_class_extracted():
    result = parse_python_file(
        TEST_PROJECT / "workspace-service/api/member_routes.py",
        "workspace-service/api/member_routes.py"
    )
    classes = {c["name"]: c for c in result["nodes"] if c["type"] == "class"}
    assert "InviteMemberRequest" in classes
    assert "BaseModel" in classes["InviteMemberRequest"]["bases"]

def test_enum_base_class_extracted():
    result = parse_python_file(
        TEST_PROJECT / "gateway/service_registry.py",
        "gateway/service_registry.py"
    )
    classes = {c["name"]: c for c in result["nodes"] if c["type"] == "class"}
    assert "ServiceStatus" in classes
    assert "Enum" in classes["ServiceStatus"]["bases"]
