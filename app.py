import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network

st.set_page_config(page_title="SET50 Shareholder Network", layout="wide")
st.title("SET50 Shareholder Network")
st.markdown("Top 5 shareholders of each SET50 company.")

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

pos = nx.spring_layout(G, seed=42, k=1.5, iterations=50)

net = Network(height="750px", width="100%", bgcolor="#FAFAFA", font_color="#333")
net.set_options('{"physics":{"enabled":false}}')

for node, data in G.nodes(data=True):
    x, y = pos[node]
    if data["type"] == "company":
        net.add_node(node, label=node, title=node, color="#1f77b4", shape="dot", size=25,
                     x=x*1000, y=y*1000)
    else:
        net.add_node(node, label=node, title=node, color="#ff7f0e", shape="square", size=15,
                     x=x*1000, y=y*1000)

for u, v, d in G.edges(data=True):
    net.add_edge(u, v, value=d["weight"], title=f'{d["weight"]:.2f}%', width=max(0.5, d["weight"]/5))

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Companies", sum(1 for _, d in G.nodes(data=True) if d["type"] == "company"))
with c2:
    st.metric("Shareholders", sum(1 for _, d in G.nodes(data=True) if d["type"] == "shareholder"))
with c3:
    st.metric("Ownership links", G.number_of_edges())

st.components.v1.html(net.generate_html(), height=800, scrolling=True)
