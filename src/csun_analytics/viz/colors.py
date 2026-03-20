"""
Consistent color palette and theme for CSUN AT Conference charts.
"""

import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------------------
# Categorical palette for topics (20+ distinct, colorblind-friendly leaning)
# ---------------------------------------------------------------------------
TOPIC_PALETTE = [
    "#1F77B4",  # blue
    "#FF7F0E",  # orange
    "#2CA02C",  # green
    "#D62728",  # red
    "#9467BD",  # purple
    "#8C564B",  # brown
    "#E377C2",  # pink
    "#7F7F7F",  # gray
    "#BCBD22",  # olive
    "#17BECF",  # teal
    "#AEC7E8",  # light blue
    "#FFBB78",  # light orange
    "#98DF8A",  # light green
    "#FF9896",  # light red
    "#C5B0D5",  # light purple
    "#C49C94",  # light brown
    "#F7B6D2",  # light pink
    "#C7C7C7",  # light gray
    "#DBDB8D",  # light olive
    "#9EDAE5",  # light teal
    "#393B79",  # dark blue
    "#637939",  # dark olive
    "#8C6D31",  # dark gold
    "#843C39",  # dark red
    "#7B4173",  # dark purple
]

# ---------------------------------------------------------------------------
# Year color map
# ---------------------------------------------------------------------------
YEAR_COLORS = {
    2023: "#636EFA",  # indigo
    2024: "#EF553B",  # coral
    2025: "#00CC96",  # emerald
    2026: "#AB63FA",  # violet
}

# ---------------------------------------------------------------------------
# Organization color map for top presenting organizations
# ---------------------------------------------------------------------------
ORG_COLORS = {
    "Amazon": "#FF9900",
    "Amazon (AWS)": "#FF9900",
    "Google": "#4285F4",
    "Microsoft": "#00A4EF",
    "Apple": "#A2AAAD",
    "Meta": "#0668E1",
    "IBM": "#0530AD",
    "Vispero": "#00838F",
    "TPGi": "#E65100",
    "Allyant": "#2E7D32",
    "Deque Systems": "#6A1B9A",
    "Deque": "#6A1B9A",
    "Level Access": "#1565C0",
    "Adobe": "#FF0000",
    "Oracle": "#F80000",
    "Samsung": "#1428A0",
    "Salesforce": "#00A1E0",
    "Intuit": "#365EBF",
    "PayPal": "#003087",
    "Mozilla": "#FF7139",
}


def get_topic_color(index: int) -> str:
    """Return a topic color by index, cycling through the palette."""
    return TOPIC_PALETTE[index % len(TOPIC_PALETTE)]


def get_org_color(org_name: str, fallback_index: int = 0) -> str:
    """Return the color for an organization, falling back to topic palette."""
    return ORG_COLORS.get(org_name, TOPIC_PALETTE[fallback_index % len(TOPIC_PALETTE)])


def build_topic_colormap(topics: list[str]) -> dict[str, str]:
    """Build a mapping from topic names to colors."""
    return {topic: get_topic_color(i) for i, topic in enumerate(topics)}


# ---------------------------------------------------------------------------
# Plotly template / layout defaults
# ---------------------------------------------------------------------------

_FONT_FAMILY = "Inter, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"

DEFAULT_LAYOUT = dict(
    autotypenumbers="convert types",
    font=dict(family=_FONT_FAMILY, size=13, color="#2E2E2E"),
    title_font=dict(family=_FONT_FAMILY, size=20, color="#1A1A2E"),
    plot_bgcolor="#FAFAFA",
    paper_bgcolor="#FFFFFF",
    margin=dict(l=60, r=40, t=80, b=60),
    hoverlabel=dict(
        bgcolor="white",
        font_size=13,
        font_family=_FONT_FAMILY,
    ),
    colorway=TOPIC_PALETTE,
    legend=dict(
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor="#E0E0E0",
        borderwidth=1,
        font=dict(size=12),
    ),
    xaxis=dict(
        type="category",
        gridcolor="#EBEBEB",
        linecolor="#CCCCCC",
        zerolinecolor="#CCCCCC",
    ),
    yaxis=dict(
        gridcolor="#EBEBEB",
        linecolor="#CCCCCC",
        zerolinecolor="#CCCCCC",
    ),
)


def apply_default_layout(fig: go.Figure, title: str = "", **overrides) -> go.Figure:
    """Apply the CSUN theme layout to a Plotly figure."""
    layout_kwargs = {**DEFAULT_LAYOUT, **overrides}
    if title:
        layout_kwargs["title_text"] = title
    fig.update_layout(**layout_kwargs)
    return fig
