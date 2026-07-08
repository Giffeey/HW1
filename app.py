import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import os
from neo4j import GraphDatabase

st.set_page_config(page_title="Data Analysis Dashboard", layout="wide")

tab1, tab2 = st.tabs(["Shareholder Network", "Centrality Analysis"])

with tab1:
    df = pd.read_csv("set50_top5_shareholders.csv")
    df["ร้อยละ (%)"] = df["ร้อยละ (%)"].astype(float)

    G = nx.Graph()
    for _, row in df.iterrows():
        co = row["สัญลักษณ์"]
        sh = row["ชื่อผู้ถือหุ้น"]
        pct = row["ร้อยละ (%)"]
        if not G.has_node(co):
            G.add_node(co, type="company", name=row["ชื่อบริษัท"])
        if not G.has_node(sh):
            G.add_node(sh, type="shareholder")
        G.add_edge(co, sh, weight=pct)

    deg = dict(G.degree())
    max_deg = max(deg.values())
    min_deg = min(deg.values())

    st.title("SET50 Shareholder Social Graph")
    st.caption("Drag nodes to explore — click any node to highlight its connections")

    c1, c2, c3 = st.columns(3)
    comps = sum(1 for n in G if G.nodes[n]["type"] == "company")
    shs = sum(1 for n in G if G.nodes[n]["type"] == "shareholder")
    c1.metric("Companies", comps)
    c2.metric("Shareholders", shs)
    c3.metric("Connections", G.number_of_edges())

    net = Network(height="700px", width="100%", bgcolor="#FFFFFF", font_color="#333")
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -2500,
          "centralGravity": 0.3,
          "springLength": 200,
          "springConstant": 0.03,
          "damping": 0.5
        },
        "stabilization": {"iterations": 100}
      },
      "interaction": {
        "hover": true,
        "hoverConnectedEdges": true,
        "selectConnectedEdges": false,
        "tooltipDelay": 100
      },
      "edges": {
        "smooth": {"type": "continuous"},
        "color": {"inherit": false}
      }
    }
    """)

    for node in G.nodes():
        d = deg[node]
        size = 10 + 25 * (d - min_deg) / (max_deg - min_deg + 1)
        if G.nodes[node]["type"] == "company":
            net.add_node(node, label=node, title=G.nodes[node]["name"],
                         color="#1a73e8", shape="dot", size=size, borderWidth=1)
        else:
            net.add_node(node, label=node, title=node,
                         color="#e8710a", shape="dot", size=size, borderWidth=1)

    for u, v, d in G.edges(data=True):
        w = d["weight"]
        width = 0.5 + 4.5 * min(w / 75, 1)
        net.add_edge(u, v, width=width, title=f"{w:.2f}%",
                     color={"color": "rgba(0,0,0,0.3)", "highlight": "rgba(0,0,0,0.6)"})

    html = net.generate_html()

    dim_js = """
    <script type="text/javascript">
      document.addEventListener("DOMContentLoaded", function() {
        function init() {
          var container = document.querySelector(".vis-network");
          if (!container || !container.network) { setTimeout(init, 300); return; }
          var netw = container.network;
          netw.on("select", function(params) {
            if (params.nodes.length === 0) {
              netw.body.data.nodes.forEach(function(n) { netw.body.data.nodes.update({id:n.id, opacity:1.0}); });
              netw.body.data.edges.forEach(function(e) { netw.body.data.edges.update({id:e.id, opacity:1.0, color:{opacity:1}}); });
              return;
            }
            var sid = params.nodes[0];
            var connected = new Set([sid]);
            var ce = netw.getConnectedEdges(sid);
            ce.forEach(function(eid) {
              var cn = netw.getConnectedNodes(eid);
              cn.forEach(function(nid) { connected.add(nid); });
            });
            netw.body.data.nodes.forEach(function(n) {
              netw.body.data.nodes.update({id:n.id, opacity: connected.has(n.id) ? 1.0 : 0.1});
            });
            var ceSet = new Set(ce);
            netw.body.data.edges.forEach(function(e) {
              var op = ceSet.has(e.id) ? 1.0 : 0.02;
              netw.body.data.edges.update({id:e.id, opacity:op, color:{opacity:op}});
            });
          });
        }
        init();
      });
    </script>
    """
    html = html.replace("</body>", dim_js + "</body>")

    st.components.v1.html(html, height=700, scrolling=True)

    deg_c = nx.degree_centrality(G)
    close_c = nx.closeness_centrality(G)
    btwn_c = nx.betweenness_centrality(G, k=min(50, G.number_of_nodes() - 1))
    eigen_c = nx.eigenvector_centrality(G, max_iter=1000)
    katz_c = nx.katz_centrality(G, alpha=0.005, beta=1.0, max_iter=2000)

    rows = []
    for n in G.nodes():
        rows.append({
            "Node": n,
            "Type": G.nodes[n]["type"].capitalize(),
            "Degree": deg[n],
            "Degree Centrality": round(deg_c.get(n, 0), 4),
            "Closeness": round(close_c.get(n, 0), 4),
            "Betweenness": round(btwn_c.get(n, 0), 4),
            "Eigenvector": round(eigen_c.get(n, 0), 4),
            "Katz": round(katz_c.get(n, 0), 4),
        })

    tbl = pd.DataFrame(rows).sort_values("Degree", ascending=False).reset_index(drop=True)
    with st.expander("Centrality Table", expanded=False):
        st.dataframe(tbl, use_container_width=True, hide_index=True)

with tab2:
    NEO4J_URI = st.secrets.get("NEO4J_URI", os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    NEO4J_USER = st.secrets.get("NEO4J_USER", os.environ.get("NEO4J_USER", "neo4j"))
    NEO4J_PASSWORD = st.secrets.get("NEO4J_PASSWORD", os.environ.get("NEO4J_PASSWORD", "password"))

    st.title("Web Graph Centrality Analysis (Neo4j Cypher)")
    st.caption("quotes_2009-04.txt — 5 measures via GDS, Betweenness & Bridges via Cypher heuristics")

    if not NEO4J_URI:
        st.info(
            "Configure Neo4j connection to enable Cypher-based centrality:\n\n"
            "1. Set up a Neo4j instance (AuraDB free tier works, enable GDS plugin)\n"
            "2. Create `.streamlit/secrets.toml`:\n"
            "```toml\n"
            'NEO4J_URI = "bolt://your-instance.databases.neo4j.io:7687"\n'
            'NEO4J_USER = "neo4j"\n'
            'NEO4J_PASSWORD = "your-password"\n'
            "```\n"
            "3. Run `py import_to_neo4j.py` to load the graph"
        )
    else:
        @st.cache_data
        def compute_all():
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            results = {}

            with driver.session() as session:
                session.run("CALL gds.graph.drop('web-graph', false)").consume()
                session.run(
                    "CALL gds.graph.project('web-graph', 'Page', 'LINKS_TO', "
                    "{orientation: 'UNDIRECTED', memory: '2GB'})"
                ).consume()

                proj_rec = session.run(
                    "MATCH (p:Page) RETURN count(*) AS c"
                ).single()
                proj_count = proj_rec["c"] if proj_rec else 0

                gds_procs = [
                    ("Degree", "CALL gds.degree.stream('web-graph') YIELD nodeId, score RETURN nodeId, score"),
                    ("Closeness", "CALL gds.closeness.stream('web-graph') YIELD nodeId, score RETURN nodeId, score"),
                    ("Eigenvector", "CALL gds.eigenvector.stream('web-graph') YIELD nodeId, score RETURN nodeId, score"),
                    ("PageRank", "CALL gds.pageRank.stream('web-graph') YIELD nodeId, score RETURN nodeId, score"),
                    ("Louvain", "CALL gds.louvain.stream('web-graph') YIELD nodeId, communityId RETURN nodeId, communityId"),
                ]

                for label, query in gds_procs:
                    results[label] = list(session.run(query))

                # Betweenness approximation via Cypher
                results["Betweenness"] = list(session.run(
                    "MATCH (a)-[:LINKS_TO]-(b)-[:LINKS_TO]-(c) "
                    "WHERE a <> c RETURN b.id AS url, count(*) AS score"
                ))

                # Bridges: find edges between Louvain communities
                comm_edges = list(session.run(
                    "MATCH (a)-[:LINKS_TO]-(b) "
                    "RETURN a.id AS src, b.id AS dst"
                ))

                node_id_map = {}
                for r in session.run("MATCH (p:Page) RETURN id(p) AS nodeId, p.id AS url"):
                    node_id_map[r["nodeId"]] = r["url"]

                session.run("CALL gds.graph.drop('web-graph', false)").consume()

            driver.close()

            # Compute bridges from Louvain communities + edges
            node_url_map = node_id_map
            louvain_data = {}
            for r in results["Louvain"]:
                url = node_url_map.get(r["nodeId"], f"node_{r['nodeId']}")
                louvain_data[url] = r["communityId"]

            neighbor_comms = {}
            for r in comm_edges:
                s, d = r["src"], r["dst"]
                sc = louvain_data.get(s)
                dc = louvain_data.get(d)
                if sc is not None and dc is not None:
                    neighbor_comms.setdefault(s, set()).add(dc)
                    neighbor_comms.setdefault(d, set()).add(sc)

            bridge_set = set()
            for url, comms in neighbor_comms.items():
                if len(comms) > 1:
                    bridge_set.add(url)

            results["Bridge"] = bridge_set
            results["_node_url_map"] = node_url_map
            results["_louvain_data"] = louvain_data
            return results, proj_count

        with st.spinner("Running GDS + Cypher algorithms…"):
            gds_results, proj_count = compute_all()

        deg_map = {}
        close_map = {}
        eigen_map = {}
        pr_map = {}
        comm_map = gds_results["_louvain_data"]
        node_url_map = gds_results["_node_url_map"]
        btwn_map = {}
        bridge_set = gds_results["Bridge"]

        for r in gds_results["Degree"]:
            url = node_url_map.get(r["nodeId"], f"node_{r['nodeId']}")
            deg_map[url] = r["score"]
        for r in gds_results["Closeness"]:
            url = node_url_map.get(r["nodeId"], f"node_{r['nodeId']}")
            close_map[url] = r["score"]
        for r in gds_results["Eigenvector"]:
            url = node_url_map.get(r["nodeId"], f"node_{r['nodeId']}")
            eigen_map[url] = r["score"]
        for r in gds_results["PageRank"]:
            url = node_url_map.get(r["nodeId"], f"node_{r['nodeId']}")
            pr_map[url] = r["score"]
        for r in gds_results["Betweenness"]:
            btwn_map[r["url"]] = r["score"]

        all_urls = set(deg_map)

        st.subheader("Graph Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Nodes (URLs)", len(all_urls))
        c2.metric("Edges in projection", proj_count)
        c3.metric("Measures", "7 (Degree, Closeness, Betweenness*, Eigenvector, PageRank, Louvain, Bridges*)")
        st.caption("*Betweenness via 2-hop Cypher heuristic; Bridges via Louvain multi-community detection")

        rows = []
        for url in sorted(all_urls, key=lambda u: -deg_map.get(u, 0)):
            rows.append({
                "Node": url[:80],
                "Degree": round(deg_map.get(url, 0), 6),
                "Closeness": round(close_map.get(url, 0), 6),
                "Betweenness": int(btwn_map.get(url, 0)),
                "Eigenvector": round(eigen_map.get(url, 0), 6),
                "PageRank": round(pr_map.get(url, 0), 6),
                "Bridge": "Yes" if url in bridge_set else "",
                "Community": comm_map.get(url, -1),
            })

        tbl2 = pd.DataFrame(rows)
        with st.expander("Centrality Table", expanded=False):
            st.dataframe(tbl2, use_container_width=True, hide_index=True)

        st.subheader("Graph Visualization (top 200 nodes by degree)")

        focus_nodes = [u for u, _ in sorted(deg_map.items(), key=lambda x: -x[1])[:200]]
        focus_set = set(focus_nodes)

        focus_deg = {u: deg_map.get(u, 0) for u in focus_nodes}
        max_d = max(focus_deg.values()) if focus_deg else 1
        min_d = min(focus_deg.values()) if focus_deg else 1

        palette = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
                   "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
                   "#469990", "#dcbeff", "#9A6324", "#fffac8", "#800000",
                   "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9"]

        net2 = Network(height="750px", width="100%", bgcolor="#FFFFFF", font_color="#333")
        net2.set_options("""
        {
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -2000,
              "centralGravity": 0.3,
              "springLength": 180,
              "springConstant": 0.04,
              "damping": 0.5
            },
            "stabilization": {"iterations": 150}
          },
          "interaction": {"hover": true, "tooltipDelay": 100},
          "edges": {
            "smooth": {"type": "continuous"},
            "color": {"inherit": false, "opacity": 0.25},
            "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}}
          }
        }
        """)

        for url in focus_nodes:
            d = focus_deg.get(url, 0)
            sz = 8 + 22 * (d - min_d) / (max_d - min_d + 1)
            comm_id = comm_map.get(url, 0)
            color = palette[comm_id % len(palette)]
            net2.add_node(url, label="", title=f"{url[:100]}\nCom:{comm_id} Deg:{d:.4f}",
                          color=color, shape="dot", size=sz, borderWidth=0)

        driver2 = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver2.session() as session:
            for url in focus_nodes:
                for r in session.run(
                    "MATCH (a:Page {id: $url})-[:LINKS_TO]-(b:Page) "
                    "WHERE b.id IN $focus RETURN b.id AS neighbor",
                    url=url, focus=list(focus_set)
                ):
                    nbr = r["neighbor"]
                    if nbr > url:
                        net2.add_edge(url, nbr, width=0.5, color="rgba(0,0,0,0.15)")
        driver2.close()

        html2 = net2.generate_html()

        dim_js2 = """
        <script type="text/javascript">
          document.addEventListener("DOMContentLoaded", function() {
            function init() {
              var container = document.querySelector(".vis-network");
              if (!container || !container.network) { setTimeout(init, 300); return; }
              var netw = container.network;
              netw.on("select", function(params) {
                if (params.nodes.length === 0) {
                  netw.body.data.nodes.forEach(function(n) { netw.body.data.nodes.update({id:n.id, opacity:1.0}); });
                  netw.body.data.edges.forEach(function(e) { netw.body.data.edges.update({id:e.id, opacity:1.0, color:{opacity:1}}); });
                  return;
                }
                var sid = params.nodes[0];
                var connected = new Set([sid]);
                var ce = netw.getConnectedEdges(sid);
                ce.forEach(function(eid) {
                  var cn = netw.getConnectedNodes(eid);
                  cn.forEach(function(nid) { connected.add(nid); });
                });
                netw.body.data.nodes.forEach(function(n) {
                  netw.body.data.nodes.update({id:n.id, opacity: connected.has(n.id) ? 1.0 : 0.1});
                });
                var ceSet = new Set(ce);
                netw.body.data.edges.forEach(function(e) {
                  var op = ceSet.has(e.id) ? 1.0 : 0.02;
                  netw.body.data.edges.update({id:e.id, opacity:op, color:{opacity:op}});
                });
              });
            }
            init();
          });
        </script>
        """
        html2 = html2.replace("</body>", dim_js2 + "</body>")
        st.components.v1.html(html2, height=750, scrolling=True)
