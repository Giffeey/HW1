import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import os
import gzip
import pickle
from neo4j import GraphDatabase

st.set_page_config(page_title="Data Analysis Dashboard", layout="wide")

CACHE_FILE = "web_graph_cache.pkl.gz"

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
            path = CACHE_FILE
            if os.path.exists(path):
                with gzip.open(path, "rb") as f:
                    return pickle.load(f)
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            results = {}

            with driver.session() as session:
                session.run("CALL gds.graph.drop('web-graph', false)").consume()
                session.run(
                    "CALL gds.graph.project('web-graph', 'Page', 'LINKS_TO', "
                    "{orientation: 'UNDIRECTED', memory: '2GB'})"
                ).consume()

                proj_rec = session.run("MATCH (p:Page) RETURN count(*) AS c").single()
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

                results["Betweenness"] = list(session.run(
                    "MATCH (a)-[:LINKS_TO]-(b)-[:LINKS_TO]-(c) "
                    "WHERE a <> c RETURN b.id AS url, count(*) AS score"
                ))
                comm_edges = list(session.run(
                    "MATCH (a)-[:LINKS_TO]-(b) RETURN a.id AS src, b.id AS dst"
                ))

                node_id_map = {}
                for r in session.run("MATCH (p:Page) RETURN id(p) AS nodeId, p.id AS url"):
                    node_id_map[r["nodeId"]] = r["url"]

                session.run("CALL gds.graph.drop('web-graph', false)").consume()
            driver.close()

            louvain_data = {}
            for r in results["Louvain"]:
                url = node_id_map.get(r["nodeId"], f"node_{r['nodeId']}")
                louvain_data[url] = r["communityId"]

            neighbor_comms = {}
            for r in comm_edges:
                s, d = r["src"], r["dst"]
                sc, dc = louvain_data.get(s), louvain_data.get(d)
                if sc is not None and dc is not None:
                    neighbor_comms.setdefault(s, set()).add(dc)
                    neighbor_comms.setdefault(d, set()).add(sc)
            bridge_set = {url for url, c in neighbor_comms.items() if len(c) > 1}

            deg_map, close_map, eigen_map, pr_map, btwn_map = {}, {}, {}, {}, {}
            for r in results["Degree"]:
                deg_map[node_id_map.get(r["nodeId"], f"node_{r['nodeId']}")] = r["score"]
            for r in results["Closeness"]:
                close_map[node_id_map.get(r["nodeId"], f"node_{r['nodeId']}")] = r["score"]
            for r in results["Eigenvector"]:
                eigen_map[node_id_map.get(r["nodeId"], f"node_{r['nodeId']}")] = r["score"]
            for r in results["PageRank"]:
                pr_map[node_id_map.get(r["nodeId"], f"node_{r['nodeId']}")] = r["score"]
            for r in results["Betweenness"]:
                btwn_map[r["url"]] = r["score"]

            out = {
                "deg": deg_map, "close": close_map, "btwn": btwn_map,
                "eigen": eigen_map, "pr": pr_map,
                "comm": louvain_data, "bridge": bridge_set,
                "count": proj_count,
            }
            with gzip.open(path, "wb") as f:
                pickle.dump(out, f, protocol=pickle.HIGHEST_PROTOCOL)
            return out

        with st.spinner("Computing…"):
            data = compute_all()

        deg_map = data["deg"]
        close_map = data["close"]
        btwn_map = data["btwn"]
        eigen_map = data["eigen"]
        pr_map = data["pr"]
        comm_map = data["comm"]
        bridge_set = data["bridge"]
        proj_count = data["count"]

        all_urls = sorted(deg_map, key=lambda u: -deg_map[u])
        min_v = {k: min(v.values()) for k, v in [("Degree", deg_map), ("Closeness", close_map),
                   ("Betweenness", btwn_map), ("Eigenvector", eigen_map), ("PageRank", pr_map)]}
        max_v = {k: max(v.values()) for k, v in [("Degree", deg_map), ("Closeness", close_map),
                   ("Betweenness", btwn_map), ("Eigenvector", eigen_map), ("PageRank", pr_map)]}

        st.subheader("Filters")
        c1, c2 = st.columns([2, 1])
        with c1:
            max_nodes = st.slider("Max nodes", 10, 200, 80, help="Limit nodes shown in graph")
        with c2:
            show_bridge = st.checkbox("Bridge nodes only", False)
        with st.expander("Metric range filters"):
            fc1, fc2, fc3, fc4, fc5 = st.columns(5)
            deg_r = fc1.slider("Degree", min_value=0.0, max_value=1.0, value=(0.0, 1.0), step=0.001)
            close_r = fc2.slider("Closeness", min_value=0.0, max_value=1.0, value=(0.0, 1.0), step=0.001)
            btwn_r = fc3.slider("Betweenness", min_value=0, max_value=int(max_v["Betweenness"]),
                                value=(0, int(max_v["Betweenness"])), step=1)
            eigen_r = fc4.slider("Eigenvector", min_value=0.0, max_value=1.0, value=(0.0, 1.0), step=0.001)
            pr_r = fc5.slider("PageRank", min_value=0.0, max_value=1.0, value=(0.0, 1.0), step=0.001)

        filtered = []
        for u in all_urls:
            if (deg_r[0] <= deg_map[u] <= deg_r[1] and close_r[0] <= close_map[u] <= close_r[1]
                    and btwn_r[0] <= btwn_map.get(u, 0) <= btwn_r[1]
                    and eigen_r[0] <= eigen_map[u] <= eigen_r[1] and pr_r[0] <= pr_map[u] <= pr_r[1]
                    and (not show_bridge or u in bridge_set)):
                filtered.append(u)

        focus_nodes = filtered[:max_nodes]
        focus_set = set(focus_nodes)

        focus_deg = {u: deg_map[u] for u in focus_nodes}
        max_d = max(focus_deg.values()) if focus_deg else 1
        min_d = min(focus_deg.values()) if focus_deg else 1

        st.subheader(f"Graph ({len(focus_nodes)} nodes shown)")
        net2 = Network(height="650px", width="100%", bgcolor="#FFFFFF", font_color="#333")
        net2.set_options("""
        {
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -3000,
              "centralGravity": 0.2,
              "springLength": 220,
              "springConstant": 0.02,
              "damping": 0.6
            },
            "stabilization": {"iterations": 200}
          },
          "interaction": {"hover": true, "tooltipDelay": 100, "dragNodes": true},
          "edges": {
            "smooth": {"type": "continuous"},
            "color": {"inherit": false, "opacity": 0.5}
          },
          "nodes": {
            "font": {"size": 11, "face": "Arial", "strokeWidth": 2, "strokeColor": "#ffffff"}
          }
        }
        """)

        palette = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
                   "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
                   "#469990", "#dcbeff", "#9A6324", "#fffac8", "#800000",
                   "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9"]

        for url in focus_nodes:
            d = focus_deg[url]
            sz = 12 + 28 * (d - min_d) / (max_d - min_d + 1)
            comm_id = comm_map.get(url, 0)
            label = url.rsplit("/", 1)[-1][:25] if "/" in url else url[:25]
            net2.add_node(url, label=label, title=f"{url}\nDeg:{d:.4f} Com:{comm_id}",
                          color=palette[comm_id % len(palette)], shape="dot", size=sz, borderWidth=1)

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
                        net2.add_edge(url, nbr, width=2, color="rgba(0,0,0,0.35)")
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
        st.components.v1.html(html2, height=650, scrolling=True)

        rows = []
        for u in all_urls:
            rows.append({
                "Node": u[:80], "Degree": round(deg_map[u], 6),
                "Closeness": round(close_map[u], 6), "Betweenness": int(btwn_map.get(u, 0)),
                "Eigenvector": round(eigen_map[u], 6), "PageRank": round(pr_map[u], 6),
                "Bridge": "Yes" if u in bridge_set else "", "Community": comm_map.get(u, -1),
            })
        tbl2 = pd.DataFrame(rows)
        if st.button("Refresh data from Neo4j", type="secondary"):
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
            st.cache_data.clear()
            st.rerun()

        with st.expander("Centrality Table", expanded=False):
            st.dataframe(tbl2, use_container_width=True, hide_index=True)
