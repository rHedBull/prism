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
                    _add_function_node(name_node, node, file_path, source, result)

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
                            _add_function_node(name_node, child, file_path, source, result)

    # Interfaces and type aliases
    if node.type in ("interface_declaration", "type_alias_declaration"):
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
            })

    for child in node.children:
        # Don't recurse into function bodies for top-level extraction
        if node.type not in ("function_declaration", "arrow_function", "method_definition"):
            _extract_nodes(child, file_path, source, result)

def _add_function_node(name_node, scope_node, file_path, source, result):
    name = source[name_node.start_byte:name_node.end_byte].decode()
    loc = scope_node.end_point[0] - scope_node.start_point[0] + 1
    result.append({
        "id": f"func:{file_path}:{name}",
        "type": "function",
        "name": name,
        "file_path": file_path,
        "lines_of_code": loc,
        "start_line": scope_node.start_point[0] + 1,
        "end_line": scope_node.end_point[0] + 1,
    })

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
