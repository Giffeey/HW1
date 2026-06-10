import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network

st.set_page_config(page_title="SET50 Shareholder Network", layout="wide")

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

comps = [n for n, d in G.nodes(data=True) if d["type"] == "company"]
shs = [n for n, d in G.nodes(data=True) if d["type"] == "shareholder"]

st.title("SET50 Shareholder Network")
st.caption(f"{len(comps)} companies · {len(shs)} shareholders · {G.number_of_edges()} links — click any node to see its connections")

c1, c2, c3 = st.columns(3)
c1.metric("Companies", len(comps))
c2.metric("Shareholders", len(shs))
c3.metric("Ownership links", G.number_of_edges())

pos = nx.spring_layout(G, k=2.5, iterations=80, seed=42)

net = Network(height="700px", width="100%", bgcolor="#FFFFFF", font_color="#333")
net.set_options("""
{
  "physics": {"enabled": false},
  "interaction": {
    "hover": true,
    "hoverConnectedEdges": true,
    "selectConnectedEdges": true,
    "tooltipDelay": 0
  },
  "nodes": {
    "borderWidth": 2,
    "borderWidthSelected": 3,
    "chosen": true,
    "font": {"size": 13, "face": "Arial", "strokeWidth": 2, "strokeColor": "#ffffff"}
  },
  "edges": {
    "smooth": {"type": "continuous"},
    "chosen": true,
    "color": {"inherit": false, "opacity": 0.4}
  }
}
""")

for node, data in G.nodes(data=True):
    x, y = pos[node]
    if data["type"] == "company":
        net.add_node(node, label=node, title=node, color="#1a73e8", shape="dot", size=28,
                     x=x, y=y, borderWidth=0)
    else:
        net.add_node(node, label=node, title=node, color="#e8710a", shape="square", size=15,
                     x=x, y=y, borderWidth=0)

for u, v, d in G.edges(data=True):
    net.add_edge(u, v, width=0.8, color="rgba(0,0,0,0.15)", title=f'{d["weight"]:.2f}%')

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
