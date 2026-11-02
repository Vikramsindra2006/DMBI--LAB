"""Run with: python -m streamlit run app.py

Upload explicitly, run an analysis, then explore the same saved computation.
Changing the dataset or mining settings invalidates the previous computation.
"""
from __future__ import annotations

import hashlib
import base64
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile
import io
import time
from itertools import combinations

import streamlit as st

st.set_page_config(page_title="BasketWise | Store insights", layout="wide", initial_sidebar_state="expanded")
nav_slot = st.container(key="quick_nav")
# Show a useful screen title while scientific packages load on a first Windows run.
st.title("Store insights")
startup = st.empty()
with startup.container():
    with st.spinner("Loading analysis and chart packages. First startup can take longer…"):
        try:
            import pandas as pd
            from market_basket.charts import (overview_figures, pair_figure, rule_figures,
                recommendation_figure, itemset_size_figure, replay_figures)
            from market_basket.core import (SOURCE, benchmark, encode, frequencies, holdout,
                itemset_view, load_upload, recommend, rule_view, run_analysis, sensitivity)
            from market_basket.live import advance_cursor, replay_snapshot
        except ImportError as exc:
            st.error(f"A required package could not load: {exc}. Run the setup from this project folder.")
            st.stop()
startup.empty()
asset_dir = Path(__file__).parent
styles = (asset_dir / "assets" / "styles.css").read_text(encoding="utf-8")
for token, filename in (("__UPLOAD_IMAGE__", "grocery-upload.webp"),
                        ("__INSIGHT_IMAGE__", "grocery-insight.webp")):
    encoded = base64.b64encode((asset_dir / "static" / filename).read_bytes()).decode("ascii")
    styles = styles.replace(token, f"data:image/webp;base64,{encoded}")
st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)

PAGES = ["Upload & overview", "Mine patterns", "Explore rules", "Basket recommendations",
         "Live charts", "Live stream (simulation)", "Evaluation", "Download results", "Project guide"]
PAGE_LABELS = {
    "Upload & overview": "Store overview",
    "Mine patterns": "Product patterns",
    "Explore rules": "What sells together",
    "Basket recommendations": "Basket suggestions",
    "Live charts": "Explore charts",
    "Live stream (simulation)": "Basket replay",
    "Evaluation": "Reliability checks",
    "Download results": "Export report",
    "Project guide": "About this project",
}
KEYS = ("analysis", "analysis_signature", "evaluation", "recommendations", "recommendation_signature", "archive",
        "live_cursor", "live_running", "live_last_tick", "chart_conf")


def clear_analysis():
    for key in KEYS:
        st.session_state.pop(key, None)


def invalidate_archive():
    st.session_state.pop("archive", None)


def current_recommendations():
    signature = (tuple(st.session_state.get("basket", [])), st.session_state.get("rec_lift", 1.),
                 st.session_state.get("rec_limit", 5))
    if signature == st.session_state.get("recommendation_signature"):
        return st.session_state.get("recommendations")
    return None


def show_plot(fig, key):
    st.plotly_chart(fig, width="stretch", theme=None, key=key,
                    config={"displaylogo": False})


def show_data(frame):
    st.dataframe(frame, width="stretch", hide_index=True)


def set_page(destination):
    st.session_state.page = destination


def render_image_panel(title, description, dark=False):
    theme = "photo-panel-dark" if dark else "photo-panel-light"
    st.markdown(f'<section class="photo-panel {theme}">'
                f'<div class="photo-panel-copy"><h3>{html.escape(title)}</h3>'
                f'<p>{html.escape(description)}</p></div></section>', unsafe_allow_html=True)


def render_insight_card(title, meaning, next_step):
    """Give a non-technical reading of the nearby chart or table."""
    st.markdown(
        '<section class="insight-card" role="note">'
        f'<h3>{html.escape(title)}</h3>'
        f'<p><strong>What it shows</strong> {html.escape(meaning)}</p>'
        f'<p><strong>What to do</strong> {html.escape(next_step)}</p>'
        '</section>', unsafe_allow_html=True)


def basket_size_insight(matrix):
    sizes = matrix.sum(axis=1).value_counts()
    common_size = int(sizes.idxmax())
    count = int(sizes.max())
    noun = "category" if common_size == 1 else "categories"
    return (f"The most common basket contains {common_size} product {noun} "
            f"({count:,} of {len(matrix):,} baskets).")


def render_footer():
    st.markdown("""<footer class="store-footer">
      <div><div class="footer-title">BasketWise</div><p>Clearer baskets. Better product decisions.</p></div>
      <div class="footer-note">Use purchase patterns as ideas to test in your store.<br>Sales uplift is not measured here.</div>
    </footer>""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("""<div class="brand"><span class="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="m5 10 2 9h10l2-9H5Z"/><path d="m9 10 3-6 3 6"/><path d="M9 14v2m6-2v2"/></svg></span>
        <div><div class="brand-name">BasketWise</div><div class="brand-sub">Store insights</div></div></div>""",
        unsafe_allow_html=True)
    st.markdown("#### Add basket data")
    upload = st.file_uploader("Choose a sales basket CSV or ZIP", type=["csv", "zip"],
                              help="Select Dataset/groceries.csv or your downloaded Kaggle CSV/ZIP. No automatic file search.")
    strict = st.checkbox("Check sample dataset size", value=True,
                         help="Expect 9,835 baskets and 169 categories. Turn off for another headerless basket CSV.")
    st.markdown(f"[Get the sample grocery dataset]({SOURCE})")
    st.divider()
    page = st.radio("Workspace", PAGES, key="page", format_func=PAGE_LABELS.get)
    st.divider()
    st.markdown("#### Pattern filters")
    support_pct = st.slider("Minimum support (%)", .5, 20., 1., .5, key="support_pct")
    confidence_pct = st.slider("Minimum confidence (%)", 5., 90., 25., 5., key="confidence_pct")
    size = st.selectbox("Maximum itemset length", ["Unrestricted", "2", "3", "4", "5"], key="max_len")
    max_len = None if size == "Unrestricted" else int(size)
    st.caption("Adjust how often products must appear together before they count as a pattern.")

with nav_slot:
    st.markdown("""<div class="top-nav-brand"><span class="nav-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="m5 10 2 9h10l2-9H5Z"/><path d="m9 10 3-6 3 6"/><path d="M9 14v2m6-2v2"/></svg></span>
      <span>BasketWise <small>Store workspace</small></span></div>""", unsafe_allow_html=True)
    shortcuts = [
        ("Overview", "Upload & overview", ":material/storefront:"),
        ("Patterns", "Mine patterns", ":material/hub:"),
        ("Suggestions", "Basket recommendations", ":material/shopping_basket:"),
        ("Reports", "Download results", ":material/download:"),
    ]
    for column, (label, destination, icon) in zip(st.columns(4, gap="small"), shortcuts):
        column.button(label, icon=icon, key=f"nav_{destination}", use_container_width=True,
                      type="primary" if page == destination else "secondary",
                      on_click=set_page, args=(destination,))

st.markdown('<p class="workspace-intro">See what customers buy together and turn basket data into useful store decisions.</p>',
            unsafe_allow_html=True)

if page != "Live stream (simulation)":
    st.session_state.live_running = False

if page == "Project guide":
    st.header("What this project does")
    st.write("A retailer wants evidence for relevant product suggestions and coordinated displays. "
             "We discover co-purchase associations in shopping baskets using Apriori and FP-Growth.")
    st.markdown("**Problem → Data → Preprocessing → Algorithm → Results → Evaluation → Insights → Decision**")
    st.subheader("How to demonstrate")
    st.markdown("""1. Upload the Kaggle CSV using the sidebar.
2. Explain the basket preview and cleaning audit.
3. Open **Product patterns**, keep 1% support and 25% confidence, and select **Find product patterns**.
4. Open **Explore rules**, interpret a rule and explain support, confidence and lift.
5. Open **Basket recommendations** and try **curd** with **whole milk**.
6. Run the hold-out experiment in **Evaluation** and discuss rules that fail the screen.
7. Generate and download the results ZIP for your GitHub `Results/` folder.""")
    st.subheader("Metrics in plain language")
    show_data(pd.DataFrame([
        {"Measure": "Support", "Meaning": "Share of all baskets containing the complete combination."},
        {"Measure": "Confidence", "Meaning": "Share of antecedent baskets that also contain the consequent."},
        {"Measure": "Lift", "Meaning": "Confidence divided by the consequent's overall basket frequency."},
    ]))
    st.write("Association is not causation. No sales increase or profit uplift has been measured. "
             "Classification accuracy is not an association-rule measure.")
    st.subheader("References")
    st.markdown(f"- [Kaggle Groceries]({SOURCE})\n"
                "- [Canonical Groceries documentation](https://michael.hahsler.net/arules/reference/Groceries.html)\n"
                "- [Apriori paper](https://www.vldb.org/conf/1994/P487.PDF)\n"
                "- [mlxtend association rules](https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/association_rules/)")
    render_footer()
    st.stop()

if upload is None:
    clear_analysis()
    st.session_state.pop("dataset", None)
    st.session_state.pop("upload_signature", None)
    st.header("Bring in your sales baskets")
    render_image_panel("From checkout data to better decisions",
                       "Upload a basket file to see top products, useful pairings and ideas for the next sale.")
    st.write("Add your basket file in the sidebar to see your top products and the combinations customers buy most often. "
             "You can try the included `Dataset/groceries.csv` file first.")
    st.info("Your file should have one shopping basket per row. A CSV or ZIP works; the wide format beginning with `Item(s)` also works.")
    st.write("Then review your products, find patterns and build suggestions for the next basket.")
    render_footer()
    st.stop()

payload = upload.getvalue()
upload_signature = (hashlib.sha256(payload).hexdigest(), upload.name, strict)
if st.session_state.get("upload_signature") != upload_signature:
    clear_analysis()
    st.session_state.pop("dataset", None)
    try:
        st.session_state.dataset = load_upload(payload, upload.name, strict)
        st.session_state.upload_signature = upload_signature
        # Reset selected product names when a different dataset is uploaded.
        st.session_state.pop("basket", None)
    except ValueError as exc:
        st.error(str(exc))
        render_footer()
        st.stop()

dataset = st.session_state.dataset
signature = (dataset.sha256, support_pct, confidence_pct, max_len)
if st.session_state.get("analysis_signature") not in (None, signature):
    clear_analysis()
    st.write("**Settings changed.** Open Product patterns and find patterns again to update the results.")

if page == "Upload & overview":
    st.header("Your store at a glance")
    c1, c2, c3 = st.columns(3)
    c1.metric("Baskets reviewed", f"{len(dataset.baskets):,}")
    c2.metric("Products found", dataset.audit["distinct_categories"])
    c3.metric("Empty baskets removed", dataset.audit["empty_baskets_excluded"])
    matrix = encode(dataset.baskets)
    preview_result = {"matrix": matrix, "frequencies": frequencies(matrix)}
    top_product = preview_result["frequencies"].iloc[0]
    render_image_panel("Your most common product", f"{top_product['Product']} appears in "
                       f"{top_product['Baskets']:,} baskets ({top_product['Support (%)']:.1f}% of all baskets).")
    st.caption(f"Selected file: {dataset.filename} · Format: {dataset.input_format}")
    st.subheader("A look at your baskets")
    show_data(pd.DataFrame({"Basket": range(1, 9), "Products": [", ".join(x) for x in dataset.baskets[:8]]})
              if len(dataset.baskets) >= 8 else pd.DataFrame({"Products": [", ".join(x) for x in dataset.baskets]}))
    st.subheader("How the file was cleaned")
    show_data(pd.DataFrame({"Operation": list(dataset.audit), "Actual count": list(dataset.audit.values())}))
    st.write("Labels are trimmed and converted to lowercase. Empty products and repeated categories within one "
             "basket are removed. Identical basket contents across transactions are retained as possible separate purchases.")
    f1, f2 = overview_figures(preview_result)
    a, b = st.columns(2)
    with a:
        show_plot(f1, "overview-frequency")
        render_insight_card("Most bought products",
                            f"{top_product['Product']} appears in {top_product['Support (%)']:.1f}% of baskets. "
                            "Longer bars mean the product appears in more baskets.",
                            "Keep frequent products easy to find and stocked; use this list to plan shelf space.")
    with b:
        show_plot(f2, "overview-size")
        render_insight_card("Typical basket size", basket_size_insight(matrix),
                            "Use the typical basket size to judge whether a small add-on suggestion is practical.")
    with st.expander("Encoding and provenance"):
        st.write(f"Boolean matrix: {matrix.shape[0]:,} rows × {matrix.shape[1]} columns. True means product present.")
        st.code(dataset.sha256, language=None)
        st.write("SHA-256 identifies the uploaded CSV bytes. Matching dimensions alone do not prove identical content.")
    render_footer()
    st.stop()

if page == "Mine patterns":
    st.header("Find products bought together")
    st.write(f"At **{support_pct:g}% minimum support**, a combination needs to appear in at least "
             f"**{math.ceil(len(dataset.baskets)*support_pct/100-1e-12):,} baskets**. "
             f"A suggestion needs **{confidence_pct:g}% confidence**.")
    st.write("Use these patterns to plan nearby shelf placements or relevant basket suggestions.")
    with st.expander("How the patterns are checked"):
        st.write("Apriori and FP-Growth mine the same baskets with the same filters. The app compares their "
                 "itemsets and support values, then verifies rule counts independently.")
    if st.button("Find product patterns", type="primary", key="run_analysis"):
        clear_analysis()
        try:
            with st.spinner("Mining patterns and checking rule metrics…"):
                st.session_state.analysis = run_analysis(dataset, support_pct/100, confidence_pct/100, max_len)
            st.session_state.analysis_signature = signature
            st.session_state.evaluation = {}
        except (ValueError, MemoryError) as exc:
            st.error(f"Analysis could not finish: {exc}. Try higher support or a smaller maximum itemset length.")
    if "analysis" in st.session_state:
        result = st.session_state.analysis
        a, b, c = st.columns(3)
        a.metric("Product combinations", len(result["itemsets"]))
        b.metric("Possible suggestions", len(result["rules"]))
        c.metric("Stronger pairings", len(result["positive_rules"]))
        st.success(f"Pattern checks passed. {result['verified_rules']} suggestions were checked against basket counts.")
        strong_rules = rule_view(result["positive_rules"], len(dataset.baskets))
        if not strong_rules.empty:
            pairing = strong_rules.iloc[0]
            render_image_panel("A pairing to review",
                               f"Baskets with {pairing['Antecedent']} also contain {pairing['Consequent']} "
                               f"{pairing['Confidence (%)']:.1f}% of the time (lift {pairing['Lift']:.2f}).",
                               dark=True)
        if result["itemsets"].empty:
            st.write("No itemsets meet this support threshold. Lower support and run again.")
        elif result["rules"].empty:
            st.write("Frequent itemsets exist, but no rules meet the confidence threshold. This is a valid result.")
        show_data(result["timings"])
        st.caption("Initial timings measure mining only. Use the Evaluation page for a repeated benchmark.")
        show_data(itemset_view(result["itemsets"], len(dataset.baskets)))
        render_insight_card("How to read the combinations",
                            "Each row lists products that appeared together often enough to pass your minimum support setting. "
                            "Joint baskets is the actual number of baskets containing every product in that row.",
                            "Start with combinations supported by many baskets, then inspect their rules before trying a display or suggestion.")
    render_footer()
    st.stop()

if "analysis" not in st.session_state:
    st.header("Find patterns first")
    st.write("Open **Product patterns** in the sidebar and select **Find product patterns**. "
             "Results are always linked to the currently uploaded data and settings.")
    render_footer()
    st.stop()

result = st.session_state.analysis
matrix = result["matrix"]
evaluation = st.session_state.setdefault("evaluation", {})
st.caption(f"Current run: {support_pct:g}% support · {confidence_pct:g}% confidence · "
           f"maximum length: {max_len or 'unrestricted'}")

if page == "Explore rules":
    st.header("What sells together")
    st.write("Search the purchase pairings to find products worth placing or suggesting together.")
    positive_only = st.checkbox("Show only positive associations (lift > 1)", value=True)
    search = st.text_input("Find a product in either side of a rule", placeholder="For example: root vegetables")
    frame = rule_view(result["positive_rules"] if positive_only else result["rules"], len(matrix))
    if search.strip():
        needle = search.strip().lower()
        frame = frame[frame.Antecedent.str.contains(needle, case=False, regex=False)
                      | frame.Consequent.str.contains(needle, case=False, regex=False)]
    st.write(f"**{len(frame)} matching rules.** Percent columns are already percentages. Lift is a ratio.")
    show_data(frame.round(4))
    render_insight_card("Reading a purchase rule",
                        "A rule links products already in a basket to another product. Confidence is the share "
                        "of matching baskets that also contain the suggested product; lift compares this with its usual frequency.",
                        "Look for strong lift, useful confidence and enough joint baskets before trying a placement or suggestion.")
    if not frame.empty:
        labels = [f"{i+1}. {r.Antecedent} → {r.Consequent}" for i, r in enumerate(frame.itertuples(index=False))]
        index = st.selectbox("Explain one rule", range(len(labels)), format_func=lambda i: labels[i])
        row = frame.iloc[index]
        st.write(f"The complete combination occurs in **{int(row['Joint baskets'])} baskets** "
                 f"(**{row['Support (%)']:.2f}%** of all baskets). Among baskets containing "
                 f"**{row.Antecedent}**, **{row['Confidence (%)']:.2f}%** also contain **{row.Consequent}**. "
                 f"This conditional frequency is **{row.Lift:.2f} times** the consequent's overall frequency.")
        st.write("This is purchase association evidence. It does not prove that recommending or discounting the product increases sales.")
    f1, f2 = rule_figures(result)
    if f1 is not None:
        leading_rule = rule_view(result["positive_rules"], len(matrix)).iloc[0]
        left, right = st.columns(2)
        with left:
            show_plot(f1, "rule-lift")
            render_insight_card("Strongest relative pairings",
                                f"The leading rule is {leading_rule['Antecedent']} → {leading_rule['Consequent']} "
                                f"with lift {leading_rule['Lift']:.2f}. Lift above 1 means the suggested product "
                                "appears more often with the starting products than it does overall.",
                                "Review its joint basket count too; a high lift from few baskets can be fragile.")
        with right:
            show_plot(f2, "rule-scatter")
            render_insight_card("Reach and likelihood",
                                "Each dot is a rule. Farther right means the combination reaches more baskets; "
                                "higher means it occurs more often after the starting product. Dot size reflects lift.",
                                "Shortlist dots with both useful reach and confidence, then check them on held-out baskets.")
    show_plot(pair_figure(result), "pair-support")
    pair_names = result["frequencies"].head(8)["Product"].tolist()
    if len(pair_names) >= 2:
        product_a, product_b = max(combinations(pair_names, 2),
                                   key=lambda pair: int((matrix[pair[0]] & matrix[pair[1]]).sum()))
        pair_count = int((matrix[product_a] & matrix[product_b]).sum())
        render_insight_card("Popular product pairs",
                            f"Among the eight most common products, {product_a} and {product_b} appear together "
                            f"in {pair_count:,} baskets. The diagonal shows each product alone; other cells show pairs.",
                            "Consider testing nearby shelf placement for a common pair and measure the result.")

elif page == "Basket recommendations":
    st.header("Suggest the next product")
    st.write("Select products already in a basket. A rule matches only when its entire antecedent is present. "
             "Products already selected are excluded from the suggestions.")
    defaults = [x for x in ("curd", "whole milk") if x in matrix.columns]
    basket = st.multiselect("Products already selected", list(matrix.columns), default=defaults, key="basket")
    rec_lift = st.slider("Recommendation lift must exceed", 1., 5., 1., .1, key="rec_lift")
    limit = st.slider("Maximum suggestions", 1, 10, 5, key="rec_limit")
    if current_recommendations() is None:
        invalidate_archive()
    refresh = st.button("Suggest products", key="suggest", help="Suggestions also refresh automatically when the basket or controls change.")
    if current_recommendations() is None or refresh:
        if basket:
            st.session_state.recommendations = recommend(basket, result["rules"], matrix, rec_lift, limit)
            st.session_state.recommendation_signature = (tuple(basket), rec_lift, limit)
            invalidate_archive()
        else:
            st.session_state.pop("recommendations", None)
            st.session_state.pop("recommendation_signature", None)
            st.write("Select at least one product to see suggestions.")
    suggestions = current_recommendations()
    if suggestions is not None:
        if suggestions.empty:
            st.write("No matching positive rule at these settings. Try another basket or review the mining thresholds.")
        else:
            show_data(suggestions.round(4))
            rec_metric = st.selectbox("Recommendation chart metric", ["Confidence (%)", "Lift", "Joint baskets"])
            show_plot(recommendation_figure(suggestions, rec_metric), "recommendation-chart")
            chart_leader = suggestions.loc[suggestions[rec_metric].idxmax()]
            if rec_metric == "Confidence (%)":
                measure = f"{chart_leader['Confidence (%)']:.1f}% of matching baskets also contain it"
            elif rec_metric == "Lift":
                measure = f"its lift is {chart_leader['Lift']:.2f}, compared with its usual frequency"
            else:
                measure = f"it appeared with its matching products in {int(chart_leader['Joint baskets']):,} baskets"
            render_insight_card("Reading the suggestions",
                                f"The longest bar for {rec_metric.lower()} is {chart_leader['Product']}: {measure}.",
                                "Try one relevant suggestion first, and check stock, margin and held-out evidence before wider use.")
            first = suggestions.iloc[0]
            st.write(f"**{first.Product}** matches **{first['Matched antecedent']}**, with "
                     f"**{first['Confidence (%)']:.2f}% confidence**, **{first.Lift:.2f} lift** "
                     f"and **{int(first['Joint baskets'])} joint baskets**.")
            render_image_panel("One suggestion to consider",
                               f"When a basket includes {first['Matched antecedent']}, "
                               f"{first.Product} is a relevant product to test as a suggestion.", dark=True)
    st.caption("Recommendations demonstrate full-data rule matching. Review separate held-out validation before selecting a deployment rule.")

elif page == "Live charts":
    st.header("Explore product trends")
    st.write("These controls update the displayed charts immediately. Rule filters operate on the current mined rule set. "
             "To discover additional rules below its support or confidence floor, change the sidebar settings and find patterns again.")
    top_n = st.slider("Number of top products", 5, 30, 15, key="chart_products")
    f1, f2 = overview_figures(result, top_n)
    left, right = st.columns(2)
    most_common = result["frequencies"].iloc[0]
    with left:
        show_plot(f1, "dynamic-frequency")
        render_insight_card("Products customers choose most",
                            f"{most_common['Product']} appears in {most_common['Support (%)']:.1f}% of baskets. "
                            f"The slider changes how many products you see, not the underlying basket counts.",
                            "Use common products to prioritize availability and easy-to-find shelf positions.")
    with right:
        show_plot(f2, "dynamic-basket-size")
        render_insight_card("How full baskets tend to be", basket_size_insight(matrix),
                            "Compare add-on ideas with the typical basket; avoid treating basket size as a sales trend.")
    st.subheader("Explore rule thresholds")
    left, right = st.columns(2)
    with left:
        live_conf = st.slider("Display confidence at least (%)", float(confidence_pct), 100., float(confidence_pct), 1., key="chart_conf")
    with right:
        live_lift = st.slider("Display lift greater than", 1., 6., 1., .1, key="chart_lift")
    shown = result["rules"][(result["rules"].confidence >= live_conf/100) & (result["rules"].lift > live_lift)]
    st.metric("Rules meeting these display filters", len(shown))
    f1, f2 = rule_figures(result, shown)
    if f1 is None:
        st.write("No rules meet these display filters. Reduce confidence or lift to see more rules.")
    else:
        shown_view = rule_view(shown, len(matrix))
        shown_leader = shown_view.iloc[0]
        left, right = st.columns(2)
        with left:
            show_plot(f1, "dynamic-lift")
            render_insight_card("Relative strength after filtering",
                                f"{len(shown_view)} rules pass your display filters. The strongest shown has "
                                f"lift {shown_leader['Lift']:.2f}.",
                                "Raise the filters to focus the shortlist, then check how many baskets support each rule.")
        with right:
            show_plot(f2, "dynamic-rule-scatter")
            render_insight_card("Reach versus confidence",
                                "Rightward dots reach more baskets. Higher dots have stronger conditional frequency. "
                                "Larger dots have higher lift.",
                                "Choose candidates that balance reach and confidence, then validate them before using them in store.")
    show_plot(itemset_size_figure(result), "itemset-sizes")
    itemset_sizes = result["itemsets"].itemsets.map(len).value_counts()
    if not itemset_sizes.empty:
        common_length = int(itemset_sizes.idxmax())
        render_insight_card("How complex the patterns are",
                            f"Most frequent combinations contain {common_length} products "
                            f"({int(itemset_sizes.max()):,} combinations).",
                            "Start with shorter combinations when planning clear signs or simple basket suggestions.")

elif page == "Live stream (simulation)":
    st.header("Watch baskets add up")
    st.write("**Simulation using your uploaded baskets.** The graphs update while the app processes consecutive "
             "batches from the CSV. This is a replay of a static dataset, not a connection to live sales or a chronological trend.")
    choices = list(matrix.columns)
    left, right = st.columns(2)
    with left:
        product_a = st.selectbox("Tracked product A", choices, index=choices.index("whole milk") if "whole milk" in choices else 0, key="stream_a")
    with right:
        others = [x for x in choices if x != product_a]
        product_b = st.selectbox("Tracked product B", others, index=others.index("other vegetables") if "other vegetables" in others else 0, key="stream_b")
    left, right = st.columns(2)
    with left:
        batch = st.slider("Baskets per update", 25, 1000, 100, 25, key="stream_batch")
    with right:
        interval = st.select_slider("Refresh interval (seconds)", options=[.5, 1., 2., 5.], value=1., key="stream_interval")
    st.session_state.setdefault("live_cursor", 0)
    st.session_state.setdefault("live_running", False)
    st.session_state.setdefault("live_last_tick", 0.)

    def start_stream():
        st.session_state.live_running = True
        st.session_state.live_last_tick = 0.

    def pause_stream():
        st.session_state.live_running = False

    def reset_stream():
        st.session_state.live_running = False
        st.session_state.live_cursor = 0
        st.session_state.live_last_tick = 0.

    def step_stream():
        st.session_state.live_cursor = advance_cursor(st.session_state.live_cursor, batch, len(matrix))
        st.session_state.live_last_tick = time.monotonic()

    controls = st.columns(4)
    controls[0].button("Start replay", on_click=start_stream,
                       disabled=st.session_state.live_running or st.session_state.live_cursor >= len(matrix), key="stream_start")
    controls[1].button("Pause replay", on_click=pause_stream, disabled=not st.session_state.live_running, key="stream_pause")
    controls[2].button("Next batch", on_click=step_stream,
                       disabled=st.session_state.live_running or st.session_state.live_cursor >= len(matrix), key="stream_next")
    controls[3].button("Reset replay", on_click=reset_stream, key="stream_reset")

    @st.fragment(run_every=interval if st.session_state.live_running else None)
    def render_replay():
        now = time.monotonic()
        if st.session_state.live_running and now-st.session_state.live_last_tick >= interval:
            st.session_state.live_cursor = advance_cursor(st.session_state.live_cursor, batch, len(matrix))
            st.session_state.live_last_tick = now
            if st.session_state.live_cursor >= len(matrix):
                st.session_state.live_running = False
                st.rerun()
        cursor = st.session_state.live_cursor
        st.progress(cursor/len(matrix), text=f"{cursor:,} / {len(matrix):,} uploaded baskets processed")
        if not cursor:
            st.write("Select Start replay for automatic updates, or Next batch to advance manually.")
            return
        history, ranking, metrics = replay_snapshot(matrix, cursor, product_a, product_b, batch)
        a, b, c, d = st.columns(4)
        a.metric("Processed baskets", f"{cursor:,}")
        b.metric("Pair support", f"{metrics['support']*100:.2f}%")
        c.metric("A → B confidence", "Not yet defined" if metrics["confidence"] is None else f"{metrics['confidence']*100:.2f}%")
        d.metric("A → B lift", "Not yet defined" if metrics["lift"] is None else f"{metrics['lift']:.2f}")
        first, second = replay_figures(history, ranking, product_a, product_b)
        left, right = st.columns(2)
        with left:
            show_plot(first, "live-replay-trend")
            render_insight_card("How the sample builds up",
                                f"After {cursor:,} processed baskets, {product_a} and {product_b} occur together "
                                f"in {metrics['joint_baskets']:,} baskets ({metrics['support']*100:.1f}%). "
                                "The lines show running shares as file rows are processed, not sales over time.",
                                "Let more baskets process before judging whether the pattern is stable.")
        with right:
            show_plot(second, "live-replay-ranking")
            leader = ranking.iloc[0]
            render_insight_card("Top product so far",
                                f"{leader['Product']} appears in {int(leader['Baskets']):,} processed baskets "
                                f"({leader['Support (%)']:.1f}%). This ranking uses only the rows processed so far.",
                                "Use the completed replay or full overview for a more representative product ranking.")
        st.caption("Values are exact counts from the processed prefix. This page does not rerun frequent-itemset mining or change the full-data analysis.")
        if cursor == len(matrix):
            st.write("**Replay completed.** Reset to demonstrate it again.")
        elif not st.session_state.live_running:
            st.write("**Replay paused.** Start resumes from the current position.")
        st.download_button("Download replay snapshot CSV", history.to_csv(index=False), "basket_replay_snapshot.csv", "text/csv", key="stream_download", on_click="ignore")

    render_replay()

elif page == "Evaluation":
    st.header("Check the evidence")
    st.write(f"**Independent verification:** {result['verified_rules']} rule metrics checked against Boolean basket counts. "
             "Both algorithms agree on itemset identities and supports.")
    st.subheader("1. Repeated mining benchmark")
    st.write("Three mining-only repetitions per algorithm. Runtime comparisons depend on data, settings and hardware.")
    if st.button("Run benchmark", key="benchmark"):
        with st.spinner("Benchmarking…"):
            evaluation["benchmark"] = benchmark(matrix, result["support"], max_len)
        invalidate_archive()
    if "benchmark" in evaluation:
        show_data(evaluation["benchmark"])
        render_insight_card("Reading the speed check",
                            "The table compares typical mining time over three runs for each method on this computer.",
                            "Use the faster method for repeated analysis, but judge recommendations by their evidence, not runtime.")
    st.subheader("2. Support and confidence sensitivity")
    st.write("Compare support 0.5%, 1% and 2% with confidence 25%, 40% and 60%. The current length restriction still applies.")
    if st.button("Run sensitivity experiment", key="sensitivity"):
        with st.spinner("Comparing nine configurations…"):
            evaluation["sensitivity"] = sensitivity(matrix, max_len)
        invalidate_archive()
    if "sensitivity" in evaluation:
        show_data(evaluation["sensitivity"])
        render_insight_card("Why the filter settings matter",
                            "Lower support or confidence usually admits more combinations and rules. "
                            "Higher settings produce a shorter list with stricter evidence thresholds.",
                            "Choose a manageable shortlist with enough joint baskets, then validate the candidates.")
    st.subheader("3. Separate discovery and validation experiment")
    st.write("Use a seeded 80/20 random split. Mine only on discovery baskets, shortlist ten positive "
             "single-consequent rules and calculate their metrics on validation baskets.")
    if st.button("Run hold-out validation", key="holdout"):
        try:
            with st.spinner("Mining discovery baskets and testing the shortlist…"):
                evaluation["holdout"], evaluation["holdout_config"] = holdout(matrix, result["support"], result["confidence"], max_len)
            invalidate_archive()
        except ValueError as exc:
            st.error(str(exc))
    if "holdout" in evaluation:
        frame, config = evaluation["holdout"], evaluation["holdout_config"]
        show_data(frame.round(4))
        st.write(f"**{int(frame.Pass.sum())} of {len(frame)} shortlisted rules pass.** "
                 f"Discovery: {config['discovery_baskets']:,} baskets. Validation: {config['validation_baskets']:,} baskets.")
        st.write(f"Pass requires validation lift > 1, confidence ≥ {confidence_pct:g}% and "
                 f"at least {config['minimum_joint_count']} joint baskets ({support_pct:g}% support).")
        st.write("This is an exploratory stability screen, not classification accuracy or proof of future sales. "
                 "Failed rules remain visible so the result can be discussed honestly.")
        render_insight_card("Which patterns held up",
                            f"{int(frame.Pass.sum())} of {len(frame)} shortlisted rules pass the separate validation screen.",
                            "Favor passing rules for small store trials; review failed rules before using them in recommendations.")

elif page == "Download results":
    st.header("Take your report with you")
    st.write("The ZIP contains computed itemsets, rules, frequencies, cleaning records, run settings, "
             "offline HTML charts and PNG figures. Experiments and recommendations are included only after you run them.")
    completed = [x for x in ("benchmark", "sensitivity", "holdout") if x in evaluation]
    st.write("Evaluation completed: " + (", ".join(completed) or "none yet"))
    if st.button("Prepare results ZIP", key="prepare_export"):
        with st.spinner("Preparing tables and charts…"):
            from market_basket.exports import build_export
            st.session_state.archive = build_export(dataset, result, evaluation, current_recommendations())
    if "archive" in st.session_state:
        archive = st.session_state.archive
        st.download_button("Download Market_Basket_UI_Results.zip", archive, "Market_Basket_UI_Results.zip",
                           "application/zip", key="download_zip")
        with ZipFile(io.BytesIO(archive)) as z:
            show_data(pd.DataFrame({"Included files": z.namelist()}))
        if st.button("Save a copy in this project's Results folder", key="save_export"):
            stamp = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
            destination = Path(__file__).resolve().parent / "Results" / stamp
            try:
                destination.mkdir(parents=True, exist_ok=True)
                # All names come from our own exporter, not an uploaded archive.
                with ZipFile(io.BytesIO(archive)) as z:
                    for name in z.namelist():
                        (destination / Path(name).name).write_bytes(z.read(name))
                (destination.parent / "Market_Basket_UI_Results.zip").write_bytes(archive)
                st.write(f"**Saved.** Current results are in `Results/{stamp}/` and the ZIP is in `Results/`. Each save uses a fresh folder.")
            except OSError:
                st.error("This installation cannot write to its Results folder. Use the download button instead.")
    st.subheader("Business decision")
    st.write("Use the evidence to shortlist relevant recommendations or product-display trials. Consider supporting "
             "counts, stability, stock availability and margin. Measure actual uplift in a controlled pilot.")

render_footer()
