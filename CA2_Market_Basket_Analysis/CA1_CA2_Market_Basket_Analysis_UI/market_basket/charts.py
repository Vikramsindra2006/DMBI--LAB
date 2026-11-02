"""Interactive figures styled for the store dashboard."""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from .core import rule_view

GREEN = "#087b57"
FOREST = "#18332f"
AMBER = "#e9a83c"
MINT = "#e7f4e9"
GRID = "#e4eee7"


def style(fig, title, height=430):
    fig.update_layout(title=title, template="plotly_white", height=height,
                      paper_bgcolor="white", plot_bgcolor="white",
                      font=dict(family="Arial", size=14, color=FOREST),
                      title_font=dict(size=18, color=FOREST),
                      margin=dict(l=35, r=25, t=65, b=45),
                      colorway=[GREEN, AMBER], showlegend=False)
    fig.update_xaxes(showline=False, gridcolor=GRID, zeroline=False)
    fig.update_yaxes(showline=False, gridcolor=GRID, zeroline=False)
    return fig


def overview_figures(result, top_n=15):
    freq = result["frequencies"].head(top_n).sort_values("Baskets")
    frequency = px.bar(freq, x="Support (%)", y="Product", orientation="h",
                       hover_data=["Baskets"], color_discrete_sequence=[GREEN])
    sizes = result["matrix"].sum(axis=1).value_counts().sort_index()
    basket = go.Figure(go.Bar(x=sizes.index.tolist(), y=sizes.values.tolist(),
                             marker_color=AMBER))
    basket.update_xaxes(title_text="Distinct categories per basket")
    basket.update_yaxes(title_text="Number of baskets")
    return style(frequency, "Most frequent product categories", 530), style(basket, "Basket-size distribution", 530)


def rule_figures(result, rules=None, top_n=10):
    view = rule_view(result["positive_rules"] if rules is None else rules, len(result["matrix"]))
    if view.empty:
        return None, None
    top = view.head(top_n).copy()
    top["Rule"] = top["Antecedent"]+" → "+top["Consequent"]
    # Short IDs keep long antecedents readable. Full text remains available on hover.
    top["ID"] = [f"R{i+1}" for i in range(len(top))]
    lift = px.bar(top.iloc[::-1], x="Lift", y="ID", orientation="h",
                  hover_data=["Rule", "Joint baskets", "Confidence (%)"], color_discrete_sequence=[GREEN])
    lift.add_vline(x=1, line_dash="dash", line_color=FOREST)
    scatter = px.scatter(view, x="Support (%)", y="Confidence (%)", size="Lift",
                         hover_data=["Antecedent", "Consequent", "Lift", "Joint baskets"],
                         color_discrete_sequence=[AMBER], size_max=24)
    scatter.update_traces(marker=dict(opacity=.78, line=dict(color=FOREST, width=.8)))
    return style(lift, "Top positive rules by lift"), style(scatter, "Rule reach and conditional frequency")


def recommendation_figure(suggestions, metric="Confidence (%)"):
    """The selected basket determines the plotted suggestions on every rerun."""
    if suggestions.empty:
        return None
    frame = suggestions.sort_values(metric)
    fig = px.bar(frame, x=metric, y="Product", orientation="h",
                 hover_data=["Matched antecedent", "Joint baskets", "Confidence (%)", "Lift"],
                 color_discrete_sequence=[GREEN])
    return style(fig, "Recommendations for the current basket")


def itemset_size_figure(result):
    counts = result["itemsets"].itemsets.map(len).value_counts().sort_index()
    fig = go.Figure(go.Bar(x=counts.index.tolist(), y=counts.values.tolist(),
                           marker_color=AMBER))
    fig.update_xaxes(title_text="Products in an itemset", dtick=1)
    fig.update_yaxes(title_text="Number of frequent itemsets")
    return style(fig, "Frequent itemsets by size")


def replay_figures(history, ranking, product_a, product_b):
    trend = go.Figure()
    for name, dash, symbol, color in [(product_a, "solid", "circle", GREEN),
                                      (product_b, "dash", "square", AMBER),
                                      ("Both products", "dot", "diamond", FOREST)]:
        trend.add_trace(go.Scatter(x=history["Baskets processed"], y=history[name], name=name,
                                  mode="lines+markers", line=dict(color=color, dash=dash, width=2.5),
                                  marker=dict(color=color, symbol=symbol, size=5)))
    trend = style(trend, "Cumulative basket support during replay", 500)
    trend.update_layout(
        margin=dict(l=35, r=25, t=130, b=50),
        title=dict(y=.98, yanchor="top"),
        showlegend=True,
        legend=dict(orientation="h", x=0, xanchor="left", y=1, yanchor="bottom",
                    font=dict(size=12)),
    )
    trend.update_xaxes(title_text="Baskets processed (file order)")
    trend.update_yaxes(title_text="Support (%)", range=[0, 100])
    bars = px.bar(ranking.sort_values("Baskets"), x="Baskets", y="Product", orientation="h",
                  hover_data=["Support (%)"], color_discrete_sequence=[GREEN])
    return trend, style(bars, "Top products so far", 470)


def pair_figure(result):
    matrix = result["matrix"]
    names = result["frequencies"].head(8)["Product"].tolist()
    a = matrix[names].to_numpy(dtype=np.int64)
    values = a.T @ a / len(matrix) * 100
    fig = px.imshow(values, x=names, y=names, text_auto=".1f", aspect="auto",
                    color_continuous_scale=[[0, "#f2f8f2"], [.5, "#b5dfc5"], [1, "#70bf9d"]],
                    labels=dict(color="Support (%)"))
    fig.update_traces(textfont_color=FOREST, hovertemplate="%{y} + %{x}<br>Support: %{z:.2f}%<extra></extra>")
    return style(fig, "Product-pair support (%); diagonal = individual support", 560)
