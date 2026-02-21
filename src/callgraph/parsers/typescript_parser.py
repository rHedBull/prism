import tree_sitter_typescript as tstypescript
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser

TSX_LANGUAGE = Language(tstypescript.language_tsx())
TS_LANGUAGE = Language(tstypescript.language_typescript())
JS_LANGUAGE = Language(tsjavascript.language())

LANGUAGE_MAP = {
    "typescript": TS_LANGUAGE,
    "typescriptreact": TSX_LANGUAGE,
    "javascript": JS_LANGUAGE,
    "javascriptreact": JS_LANGUAGE,  # tree-sitter JS handles JSX
}

def parse_typescript_file(file_path, relative_path: str, language: str = None) -> dict:
    if language is None:
        if str(file_path).endswith(".tsx"):
            language = "typescriptreact"
        elif str(file_path).endswith(".ts"):
            language = "typescript"
        elif str(file_path).endswith(".jsx"):
            language = "javascriptreact"
        else:
            language = "javascript"

    lang = LANGUAGE_MAP[language]
    parser = Parser(lang)
    source = open(file_path, "rb").read()
    tree = parser.parse(source)

    nodes = []
    imports = []

    _extract_nodes(tree.root_node, relative_path, source, nodes)
    _extract_imports(tree.root_node, source, imports)

    total_lines = source.count(b"\n") + 1

    return {
        "file_path": relative_path,
        "language": language,
        "lines_of_code": total_lines,
        "nodes": nodes,
        "imports": imports,
    }

def _extract_nodes(node, file_path: str, source: bytes, result: list):
    # Function declarations: function foo() {}
    if node.type == "function_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            _add_function_node(name_node, node, file_path, source, result)

    # Arrow functions assigned to const: const foo = () => {}
    if node.type == "lexical_declaration":
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if name_node and value_node and value_node.type == "arrow_function":
                    _add_function_node(name_node, node, file_path, source, result, body_node=value_node)

    # Export default function: export default function App() {}
    if node.type == "export_statement":
        for child in node.children:
            if child.type == "function_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    _add_function_node(name_node, child, file_path, source, result)
            if child.type == "lexical_declaration":
                for sub in child.children:
                    if sub.type == "variable_declarator":
                        name_node = sub.child_by_field_name("name")
                        value_node = sub.child_by_field_name("value")
                        if name_node and value_node and value_node.type == "arrow_function":
                            _add_function_node(name_node, child, file_path, source, result, body_node=value_node)
            if child.type in ("interface_declaration", "type_alias_declaration", "class_declaration"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = source[name_node.start_byte:name_node.end_byte].decode()
                    loc = child.end_point[0] - child.start_point[0] + 1
                    node_type = _class_like_type(child)
                    result.append({
                        "id": f"class:{file_path}:{name}",
                        "type": node_type,
                        "name": name,
                        "file_path": file_path,
                        "lines_of_code": loc,
                        "start_line": child.start_point[0] + 1,
                        "end_line": child.end_point[0] + 1,
                        "cyclomatic_complexity": 1,
                        "param_count": 0,
                        "max_nesting": 0,
                    })

    # Interfaces and type aliases
    if node.type in ("interface_declaration", "type_alias_declaration"):
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source[name_node.start_byte:name_node.end_byte].decode()
            loc = node.end_point[0] - node.start_point[0] + 1
            node_type = _class_like_type(node)
            result.append({
                "id": f"class:{file_path}:{name}",
                "type": node_type,
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "cyclomatic_complexity": 1,
                "param_count": 0,
                "max_nesting": 0,
            })

    # Class declarations
    if node.type == "class_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source[name_node.start_byte:name_node.end_byte].decode()
            loc = node.end_point[0] - node.start_point[0] + 1
            result.append({
                "id": f"class:{file_path}:{name}",
                "type": "class",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "cyclomatic_complexity": 1,
                "param_count": 0,
                "max_nesting": 0,
            })

    for child in node.children:
        # Don't recurse into function bodies for top-level extraction
        if node.type not in ("function_declaration", "arrow_function", "method_definition", "export_statement"):
            _extract_nodes(child, file_path, source, result)

def _class_like_type(node):
    """Map AST node type to our schema type for class-like declarations."""
    if node.type == "interface_declaration":
        return "interface"
    if node.type == "type_alias_declaration":
        return "type_alias"
    return "class"

def _add_function_node(name_node, scope_node, file_path, source, result, body_node=None):
    name = source[name_node.start_byte:name_node.end_byte].decode()
    loc = scope_node.end_point[0] - scope_node.start_point[0] + 1

    # Extract calls from function body
    calls = []
    if body_node is None:
        # For function_declaration, body is a direct child field
        body_node = scope_node.child_by_field_name("body")
    if body_node:
        _extract_calls(body_node, source, calls)

    param_source = body_node if body_node and body_node.type == "arrow_function" else scope_node
    result.append({
        "id": f"func:{file_path}:{name}",
        "type": "function",
        "name": name,
        "file_path": file_path,
        "lines_of_code": loc,
        "start_line": scope_node.start_point[0] + 1,
        "end_line": scope_node.end_point[0] + 1,
        "calls": calls,
        "cyclomatic_complexity": _cyclomatic_complexity(body_node) if body_node else 1,
        "param_count": _param_count(param_source),
        "max_nesting": _max_nesting(body_node) if body_node else 0,
    })

def _extract_calls(node, source: bytes, result: list):
    """Extract function call names from an AST subtree."""
    if node.type == "call_expression":
        func_node = node.child_by_field_name("function")
        if func_node:
            # Simple name: foo()
            if func_node.type == "identifier":
                name = source[func_node.start_byte:func_node.end_byte].decode()
                result.append(name)
            # Member expression: obj.method() — grab the method name
            elif func_node.type == "member_expression":
                prop = func_node.child_by_field_name("property")
                if prop:
                    result.append(source[prop.start_byte:prop.end_byte].decode())

    for child in node.children:
        _extract_calls(child, source, result)

def _extract_imports(node, source: bytes, result: list):
    if node.type == "import_statement":
        source_node = node.child_by_field_name("source")
        if source_node:
            module = source[source_node.start_byte:source_node.end_byte].decode().strip("'\"")
            names = []
            for child in node.children:
                if child.type == "import_clause":
                    for sub in child.children:
                        if sub.type == "identifier":
                            names.append(source[sub.start_byte:sub.end_byte].decode())
                        elif sub.type == "named_imports":
                            for spec in sub.children:
                                if spec.type == "import_specifier":
                                    name_node = spec.child_by_field_name("name")
                                    if name_node:
                                        names.append(source[name_node.start_byte:name_node.end_byte].decode())
            result.append({"module": module, "names": names})

    for child in node.children:
        if node.type != "import_statement":
            _extract_imports(child, source, result)


def _cyclomatic_complexity(node):
    """Count decision points in an AST subtree. Base complexity = 1."""
    DECISION_TYPES = {
        "if_statement", "switch_case", "for_statement", "for_in_statement",
        "while_statement", "do_statement", "catch_clause", "ternary_expression",
    }
    count = 1
    def _walk(n):
        nonlocal count
        if n.type in DECISION_TYPES:
            count += 1
        if n.type == "binary_expression":
            # Check for && or || operators
            if len(n.children) > 1:
                op_node = n.children[1]
                op_text = n.text[op_node.start_byte - n.start_byte:op_node.end_byte - n.start_byte]
                if op_text in (b'&&', b'||'):
                    count += 1
        for child in n.children:
            _walk(child)
    _walk(node)
    return count


def _param_count(node):
    """Count parameters of a function/arrow function node."""
    params = node.child_by_field_name("parameters")
    if not params:
        for child in node.children:
            if child.type == "formal_parameters":
                params = child
                break
    if not params:
        return 0
    count = 0
    for child in params.children:
        if child.type in ("required_parameter", "optional_parameter",
                          "rest_parameter", "identifier", "assignment_pattern"):
            count += 1
    return count


def _max_nesting(node, depth=0):
    """Compute maximum nesting depth of control structures."""
    NESTING_TYPES = {
        "if_statement", "for_statement", "for_in_statement",
        "while_statement", "do_statement", "try_statement",
        "switch_statement", "arrow_function", "function_declaration",
    }
    max_depth = depth
    for child in node.children:
        child_depth = depth + 1 if child.type in NESTING_TYPES else depth
        max_depth = max(max_depth, _max_nesting(child, child_depth))
    return max_depth
