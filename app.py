import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import tempfile
import os

st.set_page_config(page_title="SET50 Shareholder Network", layout="wide")

st.title("SET50 Shareholder Network")
st.markdown("Mapping top 5 shareholders of each SET50 company.")

CSV_PATH = "set50_top5_shareholders.csv"

@st.cache_data
def load_data():
    df = pd.read_csv(CSV_PATH)
    df["Percentage (%)"] = df["Percentage (%)"].str.replace("%", "").astype(float)
    return df

@st.cache_data
def build_graph(_df):
    G = nx.Graph()
    for _, row in _df.iterrows():
        co = row["Company Ticker"]
        sh = row["Shareholder Name"]
        pct = row["Percentage (%)"]
        if not G.has_node(co):
            G.add_node(co, type="company")
        if not G.has_node(sh):
            G.add_node(sh, type="shareholder")
        G.add_edge(co, sh, weight=pct)
    return G

df = load_data()
G = build_graph(df)

companies = sorted(df["Company Ticker"].unique())
shareholders = sorted(df["Shareholder Name"].unique())
total_links = len(df)

# ── Sidebar ──
st.sidebar.header("Controls")
min_pct = st.sidebar.slider("Min ownership (%)", 0.0, 50.0, 0.0, 0.5)
highlight_co = st.sidebar.selectbox("Highlight company", ["All"] + companies)
layout = st.sidebar.radio("Layout", ["Force-directed", "Hierarchical"])

# ── Filter ──
fdf = df[df["Percentage (%)"] >= min_pct]
if highlight_co != "All":
    fdf = fdf[fdf["Company Ticker"] == highlight_co]

H = nx.Graph()
for _, row in fdf.iterrows():
    co = row["Company Ticker"]
    sh = row["Shareholder Name"]
    pct = row["Percentage (%)"]
    if not H.has_node(co):
        H.add_node(co, type="company")
    if not H.has_node(sh):
        H.add_node(sh, type="shareholder")
    H.add_edge(co, sh, weight=pct)

# ── PyVis ──
net = Network(height="750px", width="100%", bgcolor="#FAFAFA", font_color="#333")

if layout == "Hierarchical":
    net.set_options('{"layout":{"hierarchical":{"enabled":true,"direction":"UD","sortMethod":"directed","nodeSpacing":150,"levelSeparation":200}},"physics":{"enabled":false},"edges":{"smooth":{"type":"cubicBezier"}}}')
else:
    net.set_options('{"physics":{"stabilization":{"iterations":100},"barnesHut":{"gravitationalConstant":-3000,"springLength":200}}}')

for node, data in H.nodes(data=True):
    if data["type"] == "company":
        net.add_node(node, label=node, title=node, color="#1f77b4", shape="dot", size=25)
    else:
        net.add_node(node, label=node, title=node, color="#ff7f0e", shape="square", size=15)

for u, v, d in H.edges(data=True):
    pct = d["weight"]
    net.add_edge(u, v, value=pct, title=f"{pct:.2f}%", width=max(0.5, pct / 5))

html_content = net.generate_html()

# ── Display ──
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Companies", H.number_of_nodes() - sum(1 for _, d in H.nodes(data=True) if d["type"] == "shareholder"))
with c2:
    st.metric("Shareholders", sum(1 for _, d in H.nodes(data=True) if d["type"] == "shareholder"))
with c3:
    st.metric("Ownership links", H.number_of_edges())
with c4:
    st.metric("Total links in CSV", total_links)

st.components.v1.html(html_content, height=800, scrolling=True)

# ── Data table ──
st.divider()
st.subheader("Ownership Data")
st.dataframe(fdf.sort_values("Percentage (%)", ascending=False), use_container_width=True, height=400)
