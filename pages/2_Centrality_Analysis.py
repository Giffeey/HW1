import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import math

st.set_page_config(page_title="Centrality Analysis", layout="wide")

FILEPATH = "quotes_2009-04.txt/quotes_2009-04.txt"

@st.cache_data
def parse_graph(max_lines=100000):
    G = nx.DiGraph()
    with open(FILEPATH, "r", encoding="utf-8", errors="replace") as f:
        cur_p = None
        cur_links = []
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
            if i >= max_lines:
                break
    return G

st.title("Web Graph Centrality Analysis (Neo4j-style)")
st.caption("From quotes_2009-04.txt — directed link graph")

with st.spinner("Parsing graph…"):
    G = parse_graph(200_000)

UG = G.to_undirected()
ncols = G.number_of_nodes()
nedges = G.number_of_edges()

st.subheader("Graph Summary")
c1, c2, c3 = st.columns(3)
c1.metric("Nodes (URLs)", ncols)
c2.metric("Directed Edges", nedges)
c3.metric("Avg Degree", f"{2 * nedges / ncols:.2f}")

with st.spinner("Computing centralities…"):
    deg_vals = nx.degree_centrality(UG)
    close_vals = nx.closeness_centrality(UG)
    btwn_vals = nx.betweenness_centrality(UG, k=min(100, UG.number_of_nodes() - 1))
    lcc_nodes = max(nx.connected_components(UG), key=len)
    lcc = UG.subgraph(lcc_nodes)
    eigen_lcc = nx.eigenvector_centrality(lcc, max_iter=1000, tol=1e-6)
    eigen_vals = {n: eigen_lcc.get(n, 0) for n in UG.nodes()}
    pr_vals = nx.pagerank(G, alpha=0.85)

    communities = list(nx.community.louvain_communities(UG, seed=42))
    node_comm = {}
    for i, c in enumerate(communities):
        for n in c:
            node_comm[n] = i

    articulation = set()
    if lcc.number_of_nodes() > 2:
        articulation = set(nx.articulation_points(lcc))

rows = []
for n in UG.nodes():
    rows.append({
        "Node": n[:80],
        "Degree": round(deg_vals.get(n, 0), 6),
        "Closeness": round(close_vals.get(n, 0), 6),
        "Betweenness": round(btwn_vals.get(n, 0), 6),
        "Eigenvector": round(eigen_vals.get(n, 0), 6),
        "PageRank": round(pr_vals.get(n, 0), 6),
        "Bridge": "Yes" if n in articulation else "",
        "Community": node_comm.get(n, -1),
    })

tbl = pd.DataFrame(rows).sort_values("Degree", ascending=False).reset_index(drop=True)
with st.expander("Centrality Table", expanded=False):
    st.dataframe(tbl, use_container_width=True, hide_index=True)

st.subheader("Graph Visualization")

focus_nodes = set()
for n, d in deg_vals.items():
    if d >= 0.02:
        focus_nodes.add(n)

if len(focus_nodes) < 10:
    focus_nodes = set(UG.nodes())

sub = UG.subgraph(focus_nodes)

focus_communities = {}
for i, c in enumerate(communities):
    for n in c:
        if n in focus_nodes:
            focus_communities[n] = i

focus_deg = {n: sub.degree(n) for n in sub.nodes()}
max_d = max(focus_deg.values()) if focus_deg else 1
min_d = min(focus_deg.values()) if focus_deg else 1

palette = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
           "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
           "#469990", "#dcbeff", "#9A6324", "#fffac8", "#800000",
           "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9"]

net = Network(height="750px", width="100%", bgcolor="#FFFFFF", font_color="#333")
net.set_options("""
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

for node in sub.nodes():
    d = focus_deg[node]
    sz = 8 + 22 * (d - min_d) / (max_d - min_d + 1)
    comm_id = focus_communities.get(node, 0)
    color = palette[comm_id % len(palette)]
    net.add_node(node, label="", title=f"{node[:100]}\nCom:{comm_id} Deg:{d}",
                 color=color, shape="dot", size=sz, borderWidth=0)

for u, v in sub.edges():
    net.add_edge(u, v, width=0.5, color="rgba(0,0,0,0.15)")

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
st.components.v1.html(html, height=750, scrolling=True)
