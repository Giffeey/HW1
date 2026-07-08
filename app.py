import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network

st.set_page_config(page_title="SET50 Shareholder Social Graph", layout="wide")

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
