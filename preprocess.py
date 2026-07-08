"""Extract directed graph from quotes_2009-04.txt and save as compressed pickle.

Usage:  py preprocess.py [max_lines] [output_file]
Default: 500000 lines  ->  web_graph.pkl.gz
"""
import networkx as nx
import pickle
import gzip
import sys
import os

FILEPATH = "quotes_2009-04.txt/quotes_2009-04.txt"
MAX_LINES = int(sys.argv[1]) if len(sys.argv) > 1 else 500_000
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else "web_graph.pkl.gz"

if not os.path.exists(FILEPATH):
    print(f"Error: {FILEPATH} not found. Place the raw file there first.")
    sys.exit(1)

print(f"Reading {FILEPATH} ({MAX_LINES} lines)...")
G = nx.DiGraph()
cur_p = None
cur_links = []

with open(FILEPATH, "r", encoding="utf-8", errors="replace") as f:
    for i, line in enumerate(f):
        line = line.rstrip("\n\r")
        if not line:
            if cur_p and cur_links:
                for l in cur_links:
                    G.add_edge(cur_p, l)
            cur_links = []
            cur_p = None
            continue
        if line.startswith("P\t"):
            cur_p = line[2:]
            cur_links = []
        elif line.startswith("L\t"):
            cur_links.append(line[2:])
        if i >= MAX_LINES:
            break

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print(f"Saving to {OUTPUT}...")
with gzip.open(OUTPUT, "wb") as f:
    pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

size_mb = os.path.getsize(OUTPUT) / 1e6
print(f"Done — {size_mb:.2f} MB (GitHub-friendly)")
