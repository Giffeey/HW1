import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network

st.set_page_config(page_title="SET50 Shareholder Network", layout="wide")

df = pd.read_csv("set50_top5_shareholders.csv")
df["Percentage (%)"] = df["Percentage (%)"].str.replace("%", "").astype(float)

G = nx.Graph()
for _, row in df.iterrows():
    co = row["Company Ticker"]
    sh = row["Shareholder Name"]
    pct = row["Percentage (%)"]
    if not G.has_node(co):
        G.add_node(co, type="company")
    if not G.has_node(sh):
        G.add_node(sh, type="shareholder")
    G.add_edge(co, sh, weight=pct)

comps = [n for n, d in G.nodes(data=True) if d["type"] == "company"]
shs = [n for n, d in G.nodes(data=True) if d["type"] == "shareholder"]

st.title("SET50 Shareholder Network")
st.caption("50 SET50 companies · 22 unique shareholders · 250 ownership links — select a node to explore")

col1, col2, col3 = st.columns([2, 2, 3])
with col1:
    st.metric("Companies", len(comps))
with col2:
    st.metric("Shareholders", len(shs))
with col3:
    selected = st.selectbox("Filter by company or shareholder", ["None"] + sorted(comps) + sorted(shs))

if selected != "None":
    neighbors = list(G.neighbors(selected))
    edges_data = [(n, G[selected][n]["weight"]) for n in neighbors]
    node_type = G.nodes[selected]["type"]
    badge = "🏢" if node_type == "company" else "👤"
    st.markdown(f"{badge} **{selected}** · {node_type} · **{len(neighbors)}** connections")
    for nbr, pct in sorted(edges_data, key=lambda x: -x[1]):
        st.markdown(f"&nbsp;&nbsp;&nbsp;└ {nbr} ({pct:.2f}%)")

pos = nx.bipartite_layout(G, comps, scale=3000, align="vertical")

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

preselect_js = ""
if selected != "None":
    preselect_js = f"""
      var sid = "{selected}";
      var connected = new Set([sid]);
      var ce = netw.getConnectedEdges(sid);
      ce.forEach(function(eid) {{
        var cn = netw.getConnectedNodes(eid);
        cn.forEach(function(nid) {{ connected.add(nid); }});
      }});
      netw.body.data.nodes.forEach(function(n) {{
        netw.body.data.nodes.update({{id:n.id, opacity: connected.has(n.id) ? 1.0 : 0.1}});
      }});
      var ceSet = new Set(ce);
      netw.body.data.edges.forEach(function(e) {{
        var op = ceSet.has(e.id) ? 1.0 : 0.02;
        netw.body.data.edges.update({{id:e.id, opacity:op, color:{{opacity:op}}}});
      }});
"""

dim_js = f"""
<script type="text/javascript">
  document.addEventListener("DOMContentLoaded", function() {{
    function init() {{
      var container = document.querySelector(".vis-network");
      if (!container || !container.network) {{ setTimeout(init, 300); return; }}
      var netw = container.network;
      netw.on("select", function(params) {{
        if (params.nodes.length === 0) {{
          netw.body.data.nodes.forEach(function(n) {{ netw.body.data.nodes.update({{id:n.id, opacity:1.0}}); }});
          netw.body.data.edges.forEach(function(e) {{ netw.body.data.edges.update({{id:e.id, opacity:1.0, color:{{opacity:1}}}}); }});
          return;
        }}
        var sid = params.nodes[0];
        var connected = new Set([sid]);
        var ce = netw.getConnectedEdges(sid);
        ce.forEach(function(eid) {{
          var cn = netw.getConnectedNodes(eid);
          cn.forEach(function(nid) {{ connected.add(nid); }});
        }});
        netw.body.data.nodes.forEach(function(n) {{
          netw.body.data.nodes.update({{id:n.id, opacity: connected.has(n.id) ? 1.0 : 0.1}});
        }});
        var ceSet = new Set(ce);
        netw.body.data.edges.forEach(function(e) {{
          var op = ceSet.has(e.id) ? 1.0 : 0.02;
          netw.body.data.edges.update({{id:e.id, opacity:op, color:{{opacity:op}}}});
        }});
      }});
      {preselect_js}
    }}
    init();
  }});
</script>
"""
html = html.replace("</body>", dim_js + "</body>")

st.components.v1.html(html, height=700, scrolling=True)
