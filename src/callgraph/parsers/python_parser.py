import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())

def parse_python_file(file_path, relative_path: str) -> dict:
    parser = Parser(PY_LANGUAGE)
    source = open(file_path, "rb").read()
    tree = parser.parse(source)

    nodes = []
    imports = []

    _extract_nodes(tree.root_node, relative_path, source, nodes)
    _extract_imports(tree.root_node, source, imports)

    total_lines = source.count(b"\n") + 1

    return {
        "file_path": relative_path,
        "language": "python",
        "lines_of_code": total_lines,
        "nodes": nodes,
        "imports": imports,
    }

def _extract_nodes(node, file_path: str, source: bytes, result: list):
    if node.type == "class_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source[name_node.start_byte:name_node.end_byte].decode()
            loc = node.end_point[0] - node.start_point[0] + 1
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

    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source[name_node.start_byte:name_node.end_byte].decode()
            loc = node.end_point[0] - node.start_point[0] + 1
            # Extract calls from function body
            body = node.child_by_field_name("body")
            calls = []
            if body:
                _extract_calls(body, source, calls)
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

    for child in node.children:
        _extract_nodes(child, file_path, source, result)

def _extract_calls(node, source: bytes, result: list):
    """Extract simple function call names from an AST subtree."""
    if node.type == "call":
        func_node = node.child_by_field_name("function")
        if func_node:
            # Simple name: foo()
            if func_node.type == "identifier":
                name = source[func_node.start_byte:func_node.end_byte].decode()
                result.append(name)
            # Attribute access: but only grab the attribute name for dotted calls
            # like module.func() — skip self.x() and obj.method()
            elif func_node.type == "attribute":
                attr = func_node.child_by_field_name("attribute")
                obj = func_node.child_by_field_name("object")
                if attr and obj:
                    obj_name = source[obj.start_byte:obj.end_byte].decode()
                    attr_name = source[attr.start_byte:attr.end_byte].decode()
                    # Skip self/cls method calls
                    if obj_name not in ("self", "cls"):
                        result.append(attr_name)

    for child in node.children:
        _extract_calls(child, source, result)

def _extract_imports(node, source: bytes, result: list):
    if node.type == "import_from_statement":
        module_node = node.child_by_field_name("module_name")
        if module_node:
            module = source[module_node.start_byte:module_node.end_byte].decode()
            names = []
            for child in node.children:
                if child.type == "dotted_name" and child != module_node:
                    names.append(source[child.start_byte:child.end_byte].decode())
                elif child.type == "aliased_import":
                    name_child = child.child_by_field_name("name")
                    if name_child:
                        names.append(source[name_child.start_byte:name_child.end_byte].decode())
            result.append({"module": module, "names": names})

    elif node.type == "import_statement":
        for child in node.children:
            if child.type == "dotted_name":
                module = source[child.start_byte:child.end_byte].decode()
                result.append({"module": module, "names": []})

    for child in node.children:
        if node.type not in ("import_from_statement", "import_statement"):
            _extract_imports(child, source, result)


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
