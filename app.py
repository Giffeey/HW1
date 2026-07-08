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

tab = st.radio("", ["HW1 - Shareholder Network", "HW2 - Centrality Analysis"],
               horizontal=True, label_visibility="collapsed", key="active_tab")

if tab == "HW1 - Shareholder Network":
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

elif tab == "HW2 - Centrality Analysis":
    NEO4J_URI = st.secrets.get("NEO4J_URI", os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    NEO4J_USER = st.secrets.get("NEO4J_USER", os.environ.get("NEO4J_USER", "neo4j"))
    NEO4J_PASSWORD = st.secrets.get("NEO4J_PASSWORD", os.environ.get("NEO4J_PASSWORD", "password"))

    st.title("Web Graph Centrality Analysis (Neo4j Cypher)")
    st.caption("quotes_2009-04.txt — 7 measures: Degree, Closeness, Betweenness, Eigenvector, PageRank, Community (Louvain), Bridges")

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
                comm_edges_raw = list(session.run(
                    "MATCH (a)-[:LINKS_TO]-(b) RETURN a.id AS src, b.id AS dst"
                ))
                seen = set()
                comm_edges = []
                for r in comm_edges_raw:
                    s, d = r["src"], r["dst"]
                    key = (s, d) if s < d else (d, s)
                    if key not in seen:
                        seen.add(key)
                        comm_edges.append(r)

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
                "count": proj_count, "edge_count": len(comm_edges),
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
        edge_count = data.get("edge_count")
        if edge_count is None:
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
            st.cache_data.clear()
            st.rerun()

        all_urls = sorted(deg_map, key=lambda u: -deg_map[u])

        measure_data = {
            "Degree": deg_map,
            "Closeness": close_map,
            "Betweenness": btwn_map,
            "Eigenvector": eigen_map,
            "PageRank": pr_map,
            "Community (Louvain)": comm_map,
            "Bridges": bridge_set,
        }
        measure_labels = {
            "Degree": "Degree", "Closeness": "Closeness", "Betweenness": "Betweenness",
            "Eigenvector": "Eigenvector", "PageRank": "PageRank",
            "Community (Louvain)": "Community", "Bridges": "Bridge",
        }
        max_deg = max(deg_map.values()) if deg_map else 1

        selected = st.selectbox("Visualize by", list(measure_data.keys()), index=0)

        st.subheader("Filters")
        c1, c2 = st.columns([2, 1])
        with c1:
            max_nodes = st.slider("Max nodes", 10, 200, 80)
        with c2:
            show_bridge = st.checkbox("Bridge nodes only", False)

        filtered = [u for u in all_urls if not show_bridge or u in bridge_set]
        focus_nodes = filtered[:max_nodes]
        focus_set = set(focus_nodes)

        focus_vals = {}
        for u in focus_nodes:
            if selected == "Bridges":
                focus_vals[u] = 1.0 if u in bridge_set else 0.0
            elif selected == "Community (Louvain)":
                focus_vals[u] = comm_map.get(u, 0)
            else:
                focus_vals[u] = measure_data[selected].get(u, 0)

        vals_list = [v for v in focus_vals.values()]
        vmin, vmax = (min(vals_list), max(vals_list)) if vals_list else (0, 1)
        is_comm = selected == "Community (Louvain)"
        is_br = selected == "Bridges"

        st.subheader(f"Graph — {selected} ({len(focus_nodes)} nodes shown · {proj_count:,} total nodes · {edge_count:,} edges)")
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

        def val_to_color(val, lo, hi):
            if is_comm:
                return palette[int(val) % len(palette)]
            if is_br:
                return "#e6194b" if val > 0.5 else "#cccccc"
            if hi <= lo:
                return "#1a73e8"
            t = (val - lo) / (hi - lo)
            r = 0.10 + 0.85 * t + 0.65 * max(0, t - 0.5) * 2
            g = 0.45 + 0.46 * t - 1.0 * max(0, t - 0.5) * 2
            b = 0.91 - 0.91 * t + 0.20 * max(0, t - 0.5) * 2
            r, g, b = max(0, min(1, r)), max(0, min(1, g)), max(0, min(1, b))
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

        for url in focus_nodes:
            val = focus_vals[url]
            if is_comm or is_br:
                sz = 12 + 28 * (deg_map.get(url, 0) / max_deg)
            else:
                sz = 12 + 28 * ((val - vmin) / (vmax - vmin + 1e-10)) if vmax > vmin else 20
            if is_comm:
                title = f"{url}\nCommunity: {int(val)}"
            elif is_br:
                title = f"{url}\nBridge: {'Yes' if val > 0.5 else 'No'}"
            else:
                title = f"{url}\n{measure_labels[selected]}: {val:.6f}"
            label = url.rsplit("/", 1)[-1][:25] if "/" in url else url[:25]
            net2.add_node(url, label=label, title=title,
                          color=val_to_color(val, vmin, vmax), shape="dot", size=sz, borderWidth=1)

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

        if is_comm:
            st.caption("Color = community ID (each color is a different Louvain community). Size = degree.")
        elif is_br:
            st.caption("Red = bridge node (connects multiple communities). Gray = non-bridge. Size = degree.")
        else:
            st.caption("Blue → Orange = low → high value. Size = measure value.")

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
