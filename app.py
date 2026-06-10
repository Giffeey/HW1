import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import json
import tempfile
import os

st.set_page_config(page_title="SET50 Shareholder Network", layout="wide")

st.title("SET50 Shareholder Network")
st.markdown("Top 5 major shareholders of each SET50 constituent company (data sourced from Wikipedia, shareholder data is realistic reconstruction).")

# ── Real SET50 constituents (as of 2025, per Wikipedia) ──
SET50_COMPANIES = [
    {"symbol": "ADVANC", "name": "Advanced Info Service", "sector": "ICT"},
    {"symbol": "AOT", "name": "Airports of Thailand", "sector": "Transportation"},
    {"symbol": "AWC", "name": "Asset World Corp", "sector": "Property"},
    {"symbol": "BANPU", "name": "Banpu", "sector": "Energy"},
    {"symbol": "BBL", "name": "Bangkok Bank", "sector": "Banking"},
    {"symbol": "BCP", "name": "Bangchak Corporation", "sector": "Energy"},
    {"symbol": "BDMS", "name": "Bangkok Dusit Medical Services", "sector": "Healthcare"},
    {"symbol": "BEM", "name": "Bangkok Expressway and Metro", "sector": "Transportation"},
    {"symbol": "BH", "name": "Bumrungrad International Hospital", "sector": "Healthcare"},
    {"symbol": "BJC", "name": "Berli Jucker", "sector": "Commerce"},
    {"symbol": "BTS", "name": "BTS Group Holdings", "sector": "Transportation"},
    {"symbol": "CBG", "name": "Carabao Group", "sector": "Food & Beverage"},
    {"symbol": "CCET", "name": "Cal-Comp Electronics (Thailand)", "sector": "Electronics"},
    {"symbol": "COM7", "name": "Com Seven", "sector": "Commerce"},
    {"symbol": "CPALL", "name": "CP All", "sector": "Commerce"},
    {"symbol": "CPF", "name": "Charoen Pokphand Foods", "sector": "Food & Beverage"},
    {"symbol": "CPN", "name": "Central Pattana", "sector": "Property"},
    {"symbol": "CRC", "name": "Central Retail Corporation", "sector": "Commerce"},
    {"symbol": "DELTA", "name": "Delta Electronics (Thailand)", "sector": "Electronics"},
    {"symbol": "EGCO", "name": "Electricity Generating", "sector": "Energy"},
    {"symbol": "GPSC", "name": "Global Power Synergy", "sector": "Energy"},
    {"symbol": "GULF", "name": "Gulf Energy Development", "sector": "Energy"},
    {"symbol": "HMPRO", "name": "Home Product Center", "sector": "Commerce"},
    {"symbol": "IVL", "name": "Indorama Ventures", "sector": "Petrochemicals"},
    {"symbol": "KBANK", "name": "Kasikornbank", "sector": "Banking"},
    {"symbol": "KCE", "name": "KCE Electronics", "sector": "Electronics"},
    {"symbol": "KKP", "name": "Kiatnakin Phatra Bank", "sector": "Banking"},
    {"symbol": "KTB", "name": "Krungthai Bank", "sector": "Banking"},
    {"symbol": "KTC", "name": "Krungthai Card", "sector": "Finance"},
    {"symbol": "LH", "name": "Land and Houses", "sector": "Property"},
    {"symbol": "MINT", "name": "Minor International", "sector": "Food & Beverage"},
    {"symbol": "MTC", "name": "Muangthai Capital", "sector": "Finance"},
    {"symbol": "OR", "name": "PTT Oil and Retail Business", "sector": "Energy"},
    {"symbol": "OSP", "name": "Osotspa", "sector": "Food & Beverage"},
    {"symbol": "PTT", "name": "PTT", "sector": "Energy"},
    {"symbol": "PTTEP", "name": "PTT Exploration and Production", "sector": "Energy"},
    {"symbol": "PTTGC", "name": "PTT Global Chemical", "sector": "Petrochemicals"},
    {"symbol": "RATCH", "name": "Ratch Group", "sector": "Energy"},
    {"symbol": "SCB", "name": "Siam Commercial Bank", "sector": "Banking"},
    {"symbol": "SCC", "name": "Siam Cement Group", "sector": "Construction Materials"},
    {"symbol": "SCGP", "name": "SCG Packaging", "sector": "Packaging"},
    {"symbol": "TCAP", "name": "Thanachart Capital", "sector": "Banking"},
    {"symbol": "TIDLOR", "name": "Tidlor Holdings", "sector": "Finance"},
    {"symbol": "TISCO", "name": "Tisco Financial Group", "sector": "Banking"},
    {"symbol": "TLI", "name": "Thai Life Insurance", "sector": "Insurance"},
    {"symbol": "TOP", "name": "Thai Oil", "sector": "Energy"},
    {"symbol": "TRUE", "name": "True Corporation", "sector": "ICT"},
    {"symbol": "TTB", "name": "TMBThanachart Bank", "sector": "Banking"},
    {"symbol": "TU", "name": "Thai Union Group", "sector": "Food & Beverage"},
    {"symbol": "WHA", "name": "WHA Corporation", "sector": "Property"},
]

# ── Shareholder definitions ──
SHAREHOLDER_TEMPLATES = {
    "ADVANC": [
        ("Singtel Group", 23.3, "Corporate"),
        ("Thai NVDR Co., Ltd.", 12.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 8.7, "Nominee"),
        ("State Street Europe Limited", 4.2, "Institutional"),
        ("Government Pension Fund (GPF)", 3.1, "Government"),
    ],
    "AOT": [
        ("Ministry of Finance", 70.0, "Government"),
        ("Thai NVDR Co., Ltd.", 5.8, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 3.9, "Nominee"),
        ("Vayupak Fund", 2.5, "Sovereign Fund"),
        ("State Street Europe Limited", 1.8, "Institutional"),
    ],
    "AWC": [
        ("Chirathivat Family Group", 45.0, "Family"),
        ("Thai NVDR Co., Ltd.", 8.2, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.1, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
        ("Government Pension Fund (GPF)", 2.2, "Government"),
    ],
    "BANPU": [
        ("Vannarat Family Group", 25.0, "Family"),
        ("Thai NVDR Co., Ltd.", 11.3, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 8.5, "Nominee"),
        ("State Street Europe Limited", 4.1, "Institutional"),
        ("HSBC Holdings", 3.2, "Institutional"),
    ],
    "BBL": [
        ("Sophonpanich Family", 25.0, "Family"),
        ("Thai NVDR Co., Ltd.", 9.8, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 7.5, "Nominee"),
        ("State Street Europe Limited", 5.2, "Institutional"),
        ("Thai WGDP Co., Ltd.", 3.0, "Nominee"),
    ],
    "BCP": [
        ("Vayupak Fund", 22.0, "Sovereign Fund"),
        ("Thai NVDR Co., Ltd.", 10.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.8, "Nominee"),
        ("State Street Europe Limited", 4.3, "Institutional"),
        ("Social Security Office (SSO)", 3.0, "Government"),
    ],
    "BDMS": [
        ("Kanchanapas Family", 25.0, "Family"),
        ("Thai NVDR Co., Ltd.", 11.8, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 7.2, "Nominee"),
        ("State Street Europe Limited", 5.1, "Institutional"),
        ("Government Pension Fund (GPF)", 2.8, "Government"),
    ],
    "BEM": [
        ("Chirathivat Family Group", 13.5, "Family"),
        ("Thai NVDR Co., Ltd.", 9.3, "Nominee"),
        ("Ministry of Finance", 8.0, "Government"),
        ("South East Asia UK (Type C) Nominees", 5.5, "Nominee"),
        ("State Street Europe Limited", 3.2, "Institutional"),
    ],
    "BH": [
        ("Bumrungrad International Foundation", 20.0, "Foundation"),
        ("Thai NVDR Co., Ltd.", 10.2, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 8.8, "Nominee"),
        ("State Street Europe Limited", 6.3, "Institutional"),
        ("Norges Bank Investment Management", 3.5, "Institutional"),
    ],
    "BJC": [
        ("Sirivadhanabhakdi Family", 60.0, "Family"),
        ("Thai NVDR Co., Ltd.", 5.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 3.8, "Nominee"),
        ("State Street Europe Limited", 2.1, "Institutional"),
        ("Thai WGDP Co., Ltd.", 1.5, "Nominee"),
    ],
    "BTS": [
        ("Maleenond Family", 22.0, "Family"),
        ("Thai NVDR Co., Ltd.", 10.8, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.5, "Nominee"),
        ("State Street Europe Limited", 4.0, "Institutional"),
        ("Vayupak Fund", 3.1, "Sovereign Fund"),
    ],
    "CBG": [
        ("Tanthawit Family", 35.0, "Family"),
        ("Thai NVDR Co., Ltd.", 8.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.2, "Nominee"),
        ("State Street Europe Limited", 3.8, "Institutional"),
        ("BlackRock", 2.5, "Institutional"),
    ],
    "CCET": [
        ("Cal-Comp Holding Pte Ltd", 35.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 7.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.2, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
        ("Fidelity International", 2.2, "Institutional"),
    ],
    "COM7": [
        ("Suwannawong Family", 30.0, "Family"),
        ("Thai NVDR Co., Ltd.", 8.2, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.8, "Nominee"),
        ("State Street Europe Limited", 3.5, "Institutional"),
        ("Government Pension Fund (GPF)", 2.0, "Government"),
    ],
    "CPALL": [
        ("CP Group (CPB)", 40.0, "Conglomerate"),
        ("Thai NVDR Co., Ltd.", 7.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.0, "Nominee"),
        ("State Street Europe Limited", 3.2, "Institutional"),
        ("GIC Private Limited", 2.8, "Sovereign Fund"),
    ],
    "CPF": [
        ("CP Group (CPB)", 40.0, "Conglomerate"),
        ("Thai NVDR Co., Ltd.", 6.8, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.5, "Nominee"),
        ("State Street Europe Limited", 3.1, "Institutional"),
        ("Aberdeen Standard Investments", 2.0, "Institutional"),
    ],
    "CPN": [
        ("Chirathivat Family Group", 28.0, "Family"),
        ("Thai NVDR Co., Ltd.", 10.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.8, "Nominee"),
        ("State Street Europe Limited", 4.2, "Institutional"),
        ("GIC Private Limited", 3.5, "Sovereign Fund"),
    ],
    "CRC": [
        ("Chirathivat Family Group", 32.0, "Family"),
        ("Thai NVDR Co., Ltd.", 7.8, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.5, "Nominee"),
        ("State Street Europe Limited", 3.8, "Institutional"),
        ("Fidelity International", 2.5, "Institutional"),
    ],
    "DELTA": [
        ("Delta Electronics (Thailand) Group", 30.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 8.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.0, "Nominee"),
        ("State Street Europe Limited", 4.5, "Institutional"),
        ("Temasek Holdings", 3.2, "Sovereign Fund"),
    ],
    "EGCO": [
        ("Electricity Generating Authority (EGAT)", 25.0, "Government"),
        ("Thai NVDR Co., Ltd.", 8.8, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.5, "Nominee"),
        ("State Street Europe Limited", 3.5, "Institutional"),
        ("Government Pension Fund (GPF)", 2.8, "Government"),
    ],
    "GPSC": [
        ("PTT Group", 30.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 7.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.8, "Nominee"),
        ("State Street Europe Limited", 3.2, "Institutional"),
        ("Vayupak Fund", 2.5, "Sovereign Fund"),
    ],
    "GULF": [
        ("Sarath Ratanavadi Family", 45.0, "Family"),
        ("Thai NVDR Co., Ltd.", 6.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.2, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
        ("GIC Private Limited", 2.5, "Sovereign Fund"),
    ],
    "HMPRO": [
        ("Damernpong Family", 18.0, "Family"),
        ("Thai NVDR Co., Ltd.", 10.2, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 7.5, "Nominee"),
        ("State Street Europe Limited", 5.0, "Institutional"),
        ("Vanguard Group", 3.2, "Institutional"),
    ],
    "IVL": [
        ("Lohia Family Group", 30.0, "Family"),
        ("Thai NVDR Co., Ltd.", 7.2, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.8, "Nominee"),
        ("State Street Europe Limited", 4.0, "Institutional"),
        ("Norges Bank Investment Management", 2.5, "Institutional"),
    ],
    "KBANK": [
        ("Lamsam Family Group", 22.0, "Family"),
        ("Thai NVDR Co., Ltd.", 9.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 7.0, "Nominee"),
        ("State Street Europe Limited", 5.5, "Institutional"),
        ("HSBC Holdings", 3.0, "Institutional"),
    ],
    "KCE": [
        ("Pattamasaevi Family", 20.0, "Family"),
        ("Thai NVDR Co., Ltd.", 9.0, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.5, "Nominee"),
        ("State Street Europe Limited", 4.2, "Institutional"),
        ("BlackRock", 3.0, "Institutional"),
    ],
    "KKP": [
        ("Mitsubishi UFJ Financial Group", 40.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 6.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.0, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
        ("Government Pension Fund (GPF)", 2.0, "Government"),
    ],
    "KTB": [
        ("Ministry of Finance", 55.0, "Government"),
        ("Thai NVDR Co., Ltd.", 5.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 3.5, "Nominee"),
        ("State Street Europe Limited", 2.2, "Institutional"),
        ("Vayupak Fund", 2.0, "Sovereign Fund"),
    ],
    "KTC": [
        ("Krungthai Bank", 25.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 8.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.0, "Nominee"),
        ("State Street Europe Limited", 3.8, "Institutional"),
        ("Aeon Thana Sinsap (Thailand)", 15.0, "Corporate"),
    ],
    "LH": [
        ("Sophonpanich Family", 18.0, "Family"),
        ("Thai NVDR Co., Ltd.", 9.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.5, "Nominee"),
        ("State Street Europe Limited", 4.0, "Institutional"),
        ("Land and Houses Foundation", 3.0, "Foundation"),
    ],
    "MINT": [
        ("Heinecke Family", 25.0, "Family"),
        ("Thai NVDR Co., Ltd.", 8.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.0, "Nominee"),
        ("State Street Europe Limited", 4.5, "Institutional"),
        ("Fidelity International", 3.0, "Institutional"),
    ],
    "MTC": [
        ("Chuchat Family", 30.0, "Family"),
        ("Thai NVDR Co., Ltd.", 7.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.0, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
        ("SCB Asset Management", 2.5, "Institutional"),
    ],
    "OR": [
        ("PTT Group", 75.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 3.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 2.5, "Nominee"),
        ("State Street Europe Limited", 1.5, "Institutional"),
        ("HSBC Holdings", 1.0, "Institutional"),
    ],
    "OSP": [
        ("Bhirombhakdi Family", 40.0, "Family"),
        ("Thai NVDR Co., Ltd.", 6.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.5, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
        ("Government Pension Fund (GPF)", 2.5, "Government"),
    ],
    "PTT": [
        ("Ministry of Finance", 51.0, "Government"),
        ("Vayupak Fund", 10.0, "Sovereign Fund"),
        ("Thai NVDR Co., Ltd.", 5.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.0, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
    ],
    "PTTEP": [
        ("PTT Group", 65.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 4.0, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 3.0, "Nominee"),
        ("State Street Europe Limited", 2.0, "Institutional"),
        ("Vayupak Fund", 1.8, "Sovereign Fund"),
    ],
    "PTTGC": [
        ("PTT Group", 48.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 5.0, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 3.5, "Nominee"),
        ("State Street Europe Limited", 2.5, "Institutional"),
        ("Vayupak Fund", 2.0, "Sovereign Fund"),
    ],
    "RATCH": [
        ("Electricity Generating Authority (EGAT)", 25.0, "Government"),
        ("Thai NVDR Co., Ltd.", 8.0, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.5, "Nominee"),
        ("State Street Europe Limited", 3.5, "Institutional"),
        ("Government Pension Fund (GPF)", 2.8, "Government"),
    ],
    "SCB": [
        ("CP Group (CPB)", 23.0, "Conglomerate"),
        ("Thai NVDR Co., Ltd.", 8.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.0, "Nominee"),
        ("State Street Europe Limited", 4.5, "Institutional"),
        ("HSBC Holdings", 3.0, "Institutional"),
    ],
    "SCC": [
        ("SCG Group (Crown Property)", 30.0, "Foundation"),
        ("Thai NVDR Co., Ltd.", 7.8, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.5, "Nominee"),
        ("State Street Europe Limited", 4.0, "Institutional"),
        ("Government Pension Fund (GPF)", 2.5, "Government"),
    ],
    "SCGP": [
        ("SCG Group (Crown Property)", 40.0, "Foundation"),
        ("Thai NVDR Co., Ltd.", 5.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.0, "Nominee"),
        ("State Street Europe Limited", 2.8, "Institutional"),
        ("BlackRock", 2.0, "Institutional"),
    ],
    "TCAP": [
        ("Thanachart Capital Group", 25.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 8.0, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.5, "Nominee"),
        ("State Street Europe Limited", 3.5, "Institutional"),
        ("Government Pension Fund (GPF)", 2.0, "Government"),
    ],
    "TIDLOR": [
        ("Bank of Ayudhya (Krungsri)", 45.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 5.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 3.5, "Nominee"),
        ("State Street Europe Limited", 2.5, "Institutional"),
        ("Mitsubishi UFJ Financial Group", 5.0, "Corporate"),
    ],
    "TISCO": [
        ("TISCO Group Foundation", 30.0, "Foundation"),
        ("Thai NVDR Co., Ltd.", 7.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.0, "Nominee"),
        ("State Street Europe Limited", 3.5, "Institutional"),
        ("HSBC Holdings", 2.5, "Institutional"),
    ],
    "TLI": [
        ("Thai Life Insurance Foundation", 25.0, "Foundation"),
        ("Thai NVDR Co., Ltd.", 6.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.5, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
        ("Government Pension Fund (GPF)", 2.2, "Government"),
    ],
    "TOP": [
        ("PTT Group", 40.0, "Corporate"),
        ("Thai NVDR Co., Ltd.", 6.0, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.0, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
        ("Vayupak Fund", 2.2, "Sovereign Fund"),
    ],
    "TRUE": [
        ("CP Group (CPB)", 40.0, "Conglomerate"),
        ("Thai NVDR Co., Ltd.", 6.0, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 4.0, "Nominee"),
        ("State Street Europe Limited", 2.8, "Institutional"),
        ("China Mobile International", 18.0, "Corporate"),
    ],
    "TTB": [
        ("ING Group", 20.0, "Corporate"),
        ("Ministry of Finance", 15.0, "Government"),
        ("Thai NVDR Co., Ltd.", 8.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 5.0, "Nominee"),
        ("State Street Europe Limited", 3.0, "Institutional"),
    ],
    "TU": [
        ("Chansiri Family", 22.0, "Family"),
        ("Thai NVDR Co., Ltd.", 8.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.0, "Nominee"),
        ("State Street Europe Limited", 4.5, "Institutional"),
        ("Norges Bank Investment Management", 3.0, "Institutional"),
    ],
    "WHA": [
        ("Jaroensuk Family", 15.0, "Family"),
        ("Thai NVDR Co., Ltd.", 9.5, "Nominee"),
        ("South East Asia UK (Type C) Nominees", 6.0, "Nominee"),
        ("State Street Europe Limited", 4.0, "Institutional"),
        ("GIC Private Limited", 3.0, "Sovereign Fund"),
    ],
}

CO_SECTOR_COLORS = {
    "ICT": "#800000", "Transportation": "#9A6324", "Property": "#808000",
    "Energy": "#469990", "Banking": "#000075", "Healthcare": "#e6194B",
    "Commerce": "#f58231", "Food & Beverage": "#ffe119", "Electronics": "#3cb44b",
    "Petrochemicals": "#42d4f4", "Finance": "#4363d8", "Construction Materials": "#911eb4",
    "Packaging": "#f032e6", "Insurance": "#aaffc3", "Media": "#dcbeff",
}

SH_TYPE_COLORS = {
    "Family": "#e6194B", "Corporate": "#3cb44b", "Government": "#4363d8",
    "Institutional": "#911eb4", "Sovereign Fund": "#f032e6", "Nominee": "#469990",
    "Foundation": "#800000", "Conglomerate": "#f58231",
}


@st.cache_data
def build_graph():
    G = nx.Graph()
    for c in SET50_COMPANIES:
        G.add_node(c["symbol"], type="company", sector=c["sector"],
                   name=c["name"], label=f'{c["symbol"]}\n{c["name"]}')

    for c in SET50_COMPANIES:
        holders = SHAREHOLDER_TEMPLATES[c["symbol"]]
        for h_name, pct, h_type in holders:
            if not G.has_node(h_name):
                G.add_node(h_name, type="shareholder", sh_type=h_type, label=h_name)
            G.add_edge(c["symbol"], h_name, weight=pct)

    return G


G = build_graph()

# ── Sidebar ──
st.sidebar.header("Controls")
min_weight = st.sidebar.slider("Min ownership (%)", 0.0, 50.0, 0.0, 1.0)
highlight_sector = st.sidebar.selectbox(
    "Highlight sector", ["All"] + sorted(set(c["sector"] for c in SET50_COMPANIES))
)
layout_choice = st.sidebar.radio("Layout", ["Hierarchical", "Force-directed"])
viz_size = st.sidebar.select_slider("Graph size", options=["Small", "Medium", "Large"], value="Large")

# ── Filter edges ──
edges_to_keep = []
for u, v, d in G.edges(data=True):
    if d["weight"] >= min_weight:
        if highlight_sector == "All":
            edges_to_keep.append((u, v, d))
        else:
            n = G.nodes[u]
            if n.get("sector") == highlight_sector and n.get("type") == "company":
                edges_to_keep.append((u, v, d))

H = nx.Graph()
H.add_nodes_from(G.nodes(data=True))
H.add_edges_from(edges_to_keep)

# ── PyVis network ──
size_map = {"Small": "600px", "Medium": "800px", "Large": "1100px"}

net = Network(height=size_map[viz_size], width="100%", bgcolor="#FAFAFA", font_color="#333333")

if layout_choice == "Hierarchical":
    net.set_options("""
    {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "UD",
          "sortMethod": "directed",
          "nodeSpacing": 150,
          "levelSeparation": 200
        }
      },
      "physics": { "enabled": false },
      "edges": { "smooth": { "type": "cubicBezier" } }
    }
    """)
else:
    net.set_options("""
    {
      "physics": {
        "stabilization": { "iterations": 100 },
        "barnesHut": { "gravitationalConstant": -3000, "springLength": 200 }
      }
    }
    """)

for node, data in H.nodes(data=True):
    title = data.get("label", node)
    if data.get("type") == "company":
        sector = data.get("sector", "")
        color = CO_SECTOR_COLORS.get(sector, "#999999")
        net.add_node(node, label=node, title=f"{node}: {data.get('name','')} ({sector})",
                     color=color, shape="dot", size=25, group="company")
    else:
        sh_type = data.get("sh_type", "Unknown")
        color = SH_TYPE_COLORS.get(sh_type, "#666666")
        net.add_node(node, label=node, title=f"{node} ({sh_type})",
                     color=color, shape="square", size=15, group="shareholder")

for u, v, d in H.edges(data=True):
    pct = d["weight"]
    net.add_edge(u, v, value=pct, title=f"{pct:.1f}%", width=pct / 3 + 0.5)

# ── Show graph ──
st.divider()
st.subheader("Interactive Network Graph")
st.caption("● Circle = SET50 company (colored by sector) | ■ Square = Shareholder (colored by type)")

with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
    net.save_graph(tmp.name)
    with open(tmp.name, "r", encoding="utf-8") as f:
        html_content = f.read()
    st.components.v1.html(html_content, height=int(size_map[viz_size].replace("px", "")) + 50,
                          scrolling=True)
    os.unlink(tmp.name)

# ── Stats ──
st.divider()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Companies", sum(1 for _, d in H.nodes(data=True) if d.get("type") == "company"))
with col2:
    st.metric("Shareholders",
              sum(1 for _, d in H.nodes(data=True) if d.get("type") == "shareholder"))
with col3:
    st.metric("Ownership links", H.number_of_edges())
with col4:
    total_owned = sum(d["weight"] for _, _, d in H.edges(data=True))
    st.metric("Total ownership representation", f"{total_owned:.0f}%")

# ── Data table ──
st.divider()
st.subheader("Ownership Breakdown")
rows = []
for c in SET50_COMPANIES:
    for h_name, pct, h_type in SHAREHOLDER_TEMPLATES[c["symbol"]]:
        if pct >= min_weight:
            rows.append({
                "Company": c["symbol"],
                "Company Name": c["name"],
                "Sector": c["sector"],
                "Shareholder": h_name,
                "Type": h_type,
                "Ownership (%)": pct,
            })

df = pd.DataFrame(rows)
if highlight_sector != "All":
    df = df[df["Sector"] == highlight_sector]

st.dataframe(df.sort_values("Ownership (%)", ascending=False), use_container_width=True, height=500)

# ── Company info panel ──
st.divider()
st.subheader("Company Details")
selected = st.selectbox("Select a company", [c["symbol"] + " - " + c["name"] for c in SET50_COMPANIES])
if selected:
    sym = selected.split(" - ")[0]
    co = next(c for c in SET50_COMPANIES if c["symbol"] == sym)
    st.write(f"**{co['name']}** ({co['symbol']}) — Sector: {co['sector']}")
    holders = SHAREHOLDER_TEMPLATES[sym]
    st.table(pd.DataFrame(holders, columns=["Shareholder", "Ownership (%)", "Type"]))

st.sidebar.markdown("---")
st.sidebar.caption(
    "Company list sourced from Wikipedia (as of 2025). "
    "Shareholder data is a realistic reconstruction based on known Thai market patterns."
)
