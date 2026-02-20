import argparse
from pathlib import Path
from callgraph.graph_builder import build_graph
from callgraph.output import write_graph

def main():
    parser = argparse.ArgumentParser(description="Build code architecture graph")
    parser.add_argument("path", help="Path to the repository to analyze")
    parser.add_argument("-o", "--output", default=".callgraph", help="Output directory")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    print(f"Analyzing {root}...")

    graph = build_graph(root)
    write_graph(graph, args.output)

    print(f"Graph written to {args.output}/")
    print(f"  {len(graph['nodes'])} nodes")
    print(f"  {len(graph['edges'])} edges")

if __name__ == "__main__":
    main()
