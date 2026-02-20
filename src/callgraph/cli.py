import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Build code architecture graph")
    parser.add_argument("path", help="Path to the repository to analyze")
    parser.add_argument("-o", "--output", default=".callgraph", help="Output directory")
    args = parser.parse_args()
    print(f"Analyzing {args.path}...")

if __name__ == "__main__":
    main()
