import argparse
import functools
import http.server
from pathlib import Path

from callgraph.graph_builder import build_graph
from callgraph.output import write_graph


def cmd_build(args):
    root = Path(args.path).resolve()
    print(f"Analyzing {root}...")

    graph = build_graph(root)
    write_graph(graph, args.output)

    print(f"Graph written to {args.output}/")
    print(f"  {len(graph['nodes'])} nodes")
    print(f"  {len(graph['edges'])} edges")


def cmd_diff(args):
    """Compare two graph directories and write diff.json."""
    import json
    from callgraph.graph_diff import compute_diff

    dir_a = Path(args.graph_a) / ".callgraph"
    dir_b = Path(args.graph_b) / ".callgraph"

    graph_a = {
        "nodes": json.loads((dir_a / "nodes.json").read_text()),
        "edges": json.loads((dir_a / "edges.json").read_text()),
    }
    graph_b = {
        "nodes": json.loads((dir_b / "nodes.json").read_text()),
        "edges": json.loads((dir_b / "edges.json").read_text()),
    }

    meta = {
        "source": "commits",
        "ref_a": getattr(args, "ref_a", "unknown"),
        "ref_b": getattr(args, "ref_b", "unknown"),
    }
    diff = compute_diff(graph_a, graph_b, meta)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "diff.json").write_text(json.dumps(diff, indent=2))

    s = diff["summary"]
    print(f"Diff written to {out}/diff.json")
    print(f"  +{s['added_nodes']} added, -{s['removed_nodes']} removed, "
          f"~{s['modified_nodes']} modified, >{s['moved_nodes']} moved")


def cmd_plan(args):
    """Apply a plan to a graph and write diff.json."""
    import json
    import shutil
    from callgraph.plan_engine import apply_plan, load_plan

    graph_dir = Path(args.graph_dir) / ".callgraph"
    graph = {
        "nodes": json.loads((graph_dir / "nodes.json").read_text()),
        "edges": json.loads((graph_dir / "edges.json").read_text()),
    }

    plan = load_plan(args.plan)
    diff = apply_plan(graph, plan)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "diff.json").write_text(json.dumps(diff, indent=2))
    shutil.copy2(args.plan, out / "plan.json")

    s = diff["summary"]
    print(f"Plan '{plan.get('name', 'unnamed')}' applied.")
    print(f"  +{s['added_nodes']} added, -{s['removed_nodes']} removed, "
          f"~{s['modified_nodes']} modified, >{s['moved_nodes']} moved")
    print(f"Output: {out}/diff.json")


def cmd_serve(args):
    import shutil
    port = args.port
    web_dir = Path(__file__).parent.parent.parent / "web"
    # Copy graph data into web dir so it's served alongside the frontend
    callgraph_src = Path.cwd() / ".callgraph"
    callgraph_dst = web_dir / ".callgraph"
    if callgraph_src.exists():
        if callgraph_dst.exists():
            shutil.rmtree(callgraph_dst)
        shutil.copytree(callgraph_src, callgraph_dst)
    directory = str(web_dir)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    with http.server.HTTPServer(("", port), handler) as httpd:
        print(f"Serving at http://localhost:{port}")
        httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Build code architecture graph")
    subparsers = parser.add_subparsers(dest="command")

    # build subcommand
    build_parser = subparsers.add_parser("build", help="Build the graph from a codebase")
    build_parser.add_argument("path", help="Path to the repository to analyze")
    build_parser.add_argument("-o", "--output", default=".callgraph", help="Output directory")

    # serve subcommand
    serve_parser = subparsers.add_parser("serve", help="Start the web visualizer")
    serve_parser.add_argument("-p", "--port", type=int, default=8080, help="Port to serve on")

    # diff subcommand
    diff_parser = subparsers.add_parser("diff", help="Compare two graph directories")
    diff_parser.add_argument("graph_a", help="Path to first codebase (with .callgraph/)")
    diff_parser.add_argument("graph_b", help="Path to second codebase (with .callgraph/)")
    diff_parser.add_argument("-o", "--output", default=".callgraph", help="Output directory for diff.json")
    diff_parser.add_argument("--ref-a", default="unknown", help="Label for graph_a")
    diff_parser.add_argument("--ref-b", default="unknown", help="Label for graph_b")

    # plan subcommand
    plan_parser = subparsers.add_parser("plan", help="Apply an architectural plan and produce diff")
    plan_parser.add_argument("plan", help="Path to plan.json")
    plan_parser.add_argument("--graph-dir", default=".", help="Path to codebase with .callgraph/")
    plan_parser.add_argument("-o", "--output", default=".callgraph", help="Output directory for diff.json")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "diff":
        cmd_diff(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "serve":
        cmd_serve(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
