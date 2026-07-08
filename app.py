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
    st.caption("quotes_2009-04.txt — all measures computed via Cypher + GDS")

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
        def run_gds():
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            results = {}

            with driver.session() as session:
                session.run("CALL gds.graph.drop('web-graph', false)").consume()
                session.run(
                    "CALL gds.graph.project('web-graph', 'Page', "
                    "{LINKS_TO: {orientation: 'UNDIRECTED'}})"
                ).consume()

                proj_rec = session.run(
                    "CALL gds.graph.nodeProperties.stream('web-graph', 'id') "
                    "YIELD nodeId, propertyValue RETURN count(*) AS c"
                ).single()
                proj_count = proj_rec["c"] if proj_rec else 0

                for label, algo, query in [
                    ("Degree", "gds.degree.stream",
                     "CALL gds.degree.stream('web-graph') YIELD nodeId, score RETURN nodeId, score"),
                    ("Closeness", "gds.closeness.stream",
                     "CALL gds.closeness.stream('web-graph') YIELD nodeId, score RETURN nodeId, score"),
                    ("Betweenness", "gds.betweenness.stream",
                     "CALL gds.betweenness.stream('web-graph', {maxDepth:4}) YIELD nodeId, score RETURN nodeId, score"),
                    ("Eigenvector", "gds.eigenvector.stream",
                     "CALL gds.eigenvector.stream('web-graph') YIELD nodeId, score RETURN nodeId, score"),
                    ("PageRank", "gds.pageRank.stream",
                     "CALL gds.pageRank.stream('web-graph') YIELD nodeId, score RETURN nodeId, score"),
                    ("Louvain", "gds.louvain.stream",
                     "CALL gds.louvain.stream('web-graph') YIELD nodeId, communityId RETURN nodeId, communityId"),
                    ("Bridge", "gds.bridges.stream",
                     "CALL gds.bridges.stream('web-graph') YIELD nodeId RETURN DISTINCT nodeId"),
                ]:
                    records = list(session.run(query))
                    results[label] = records
                    session.run(f"CALL {algo}.stats('web-graph') YIELD preProcessingMillis RETURN 1").consume()

                node_id_map = {}
                for r in session.run("MATCH (p:Page) RETURN id(p) AS nodeId, p.id AS url"):
                    node_id_map[r["nodeId"]] = r["url"]

            driver.close()
            return results, node_id_map, proj_count

        with st.spinner("Running GDS centrality algorithms via Cypher…"):
            gds_results, node_id_map, proj_count = run_gds()

        deg_map = {}
        close_map = {}
        btwn_map = {}
        eigen_map = {}
        pr_map = {}
        comm_map = {}
        bridge_set = set()

        for label, out_map in [
            ("Degree", deg_map), ("Closeness", close_map),
            ("Betweenness", btwn_map), ("Eigenvector", eigen_map),
            ("PageRank", pr_map),
        ]:
            for r in gds_results[label]:
                url = node_id_map.get(r["nodeId"], f"node_{r['nodeId']}")
                out_map[url] = r["score"]

        for r in gds_results["Louvain"]:
            url = node_id_map.get(r["nodeId"], f"node_{r['nodeId']}")
            comm_map[url] = r["communityId"]

        for r in gds_results["Bridge"]:
            url = node_id_map.get(r["nodeId"], f"node_{r['nodeId']}")
            bridge_set.add(url)

        all_urls = set(deg_map)

        st.subheader("Graph Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Nodes (URLs)", len(all_urls))
        c2.metric("Edges in projection", proj_count)
        c3.metric("Measures", "7 (Degree, Closeness, Betweenness, Eigenvector, PageRank, Louvain, Bridges)")

        rows = []
        for url in sorted(all_urls, key=lambda u: -deg_map.get(u, 0)):
            rows.append({
                "Node": url[:80],
                "Degree": round(deg_map.get(url, 0), 6),
                "Closeness": round(close_map.get(url, 0), 6),
                "Betweenness": round(btwn_map.get(url, 0), 6),
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
