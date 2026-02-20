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
            result.append({
                "id": f"class:{file_path}:{name}",
                "type": "class",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
            })

    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source[name_node.start_byte:name_node.end_byte].decode()
            loc = node.end_point[0] - node.start_point[0] + 1
            result.append({
                "id": f"func:{file_path}:{name}",
                "type": "function",
                "name": name,
                "file_path": file_path,
                "lines_of_code": loc,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
            })

    for child in node.children:
        _extract_nodes(child, file_path, source, result)

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
