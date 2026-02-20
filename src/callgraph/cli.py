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


def cmd_serve(args):
    port = args.port
    directory = str(Path(__file__).parent.parent.parent / "web")
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

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "serve":
        cmd_serve(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
