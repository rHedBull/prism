import json
from pathlib import Path

def write_graph(graph: dict, output_dir: str):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "nodes.json").write_text(json.dumps(graph["nodes"], indent=2))
    (out / "edges.json").write_text(json.dumps(graph["edges"], indent=2))
