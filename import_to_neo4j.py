"""Import preprocessed web graph into Neo4j for Cypher-based centrality analysis.

Requires a running Neo4j instance (local or AuraDB).
Reads credentials from: env vars > .streamlit/secrets.toml > defaults.
"""
import os
import gzip
import pickle
from neo4j import GraphDatabase

def _read_secrets():
    try:
        with open(".streamlit/secrets.toml") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    yield k, v
    except FileNotFoundError:
        pass

secrets = dict(_read_secrets())

URI = os.environ.get("NEO4J_URI") or secrets.get("NEO4J_URI", "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER") or secrets.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD") or secrets.get("NEO4J_PASSWORD", "password")
GRAPH_PICKLE = "web_graph.pkl.gz"
BATCH = 5000

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

with gzip.open(GRAPH_PICKLE, "rb") as f:
    G = pickle.load(f)

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

with driver.session() as session:
    session.run("MATCH (n) DETACH DELETE n")
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Page) REQUIRE p.id IS UNIQUE")

    nodes = list(G.nodes())
    for i in range(0, len(nodes), BATCH):
        batch = nodes[i : i + BATCH]
        session.run(
            "UNWIND $batch AS id CREATE (:Page {id: id})", batch=batch
        )
    print(f"Created {len(nodes)} nodes")

    edges = list(G.edges())
    for i in range(0, len(edges), BATCH):
        batch = edges[i : i + BATCH]
        session.run(
            """UNWIND $batch AS e
               MATCH (a:Page {id: e[0]}), (b:Page {id: e[1]})
               CREATE (a)-[:LINKS_TO]->(b)""",
            batch=batch,
        )
    print(f"Created {len(edges)} edges")

driver.close()
print("Done. Run GDS centrality algorithms via Cypher now.")
