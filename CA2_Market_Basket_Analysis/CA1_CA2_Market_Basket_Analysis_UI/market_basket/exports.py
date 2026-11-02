"""Build a self-contained ZIP of current analysis evidence."""
from __future__ import annotations
import csv
import importlib.metadata
import io
import json
import platform
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .charts import overview_figures, pair_figure, rule_figures, itemset_size_figure, recommendation_figure
from .core import SOURCE, itemset_view, rule_view


def build_export(dataset, result, evaluation=None, recommendations=None):
    """Return ZIP bytes. No local paths are searched, and no files are written."""
    evaluation = evaluation or {}
    n = len(result["matrix"])
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "uploaded_file": dataset.filename,
        "csv_sha256": dataset.sha256, "input_format": dataset.input_format,
        "groceries_shape_matches": dataset.canonical_shape,
        "dataset_source": SOURCE if dataset.canonical_shape else "User-uploaded basket CSV; source supplied by the user",
        "baskets": n, "categories": len(result["matrix"].columns),
        "min_support": result["support"], "min_confidence": result["confidence"],
        "max_itemset_length": result["max_len"], "frequent_itemsets": len(result["itemsets"]),
        "baseline_rules": len(result["rules"]), "positive_rules": len(result["positive_rules"]),
        "algorithms_equivalent": bool(result["equivalent"]), "independently_verified_rules": result["verified_rules"],
        "evaluation_completed": list(evaluation), "holdout_configuration": evaluation.get("holdout_config"),
        "business_trial": "Not performed. Associations do not establish causal sales or profit uplift.",
    }
    versions = {x: importlib.metadata.version(x) for x in ("streamlit", "pandas", "numpy", "mlxtend", "plotly", "matplotlib")}
    versions["python"] = platform.python_version()
    tables = {
        "frequent_itemsets.csv": itemset_view(result["itemsets"], n),
        "all_association_rules.csv": rule_view(result["rules"], n),
        "positive_rules.csv": rule_view(result["positive_rules"], n),
        "item_frequencies.csv": result["frequencies"], "initial_algorithm_timings.csv": result["timings"],
    }
    for key, name in [("benchmark", "algorithm_benchmark.csv"), ("sensitivity", "threshold_sensitivity.csv"),
                      ("holdout", "holdout_validation.csv")]:
        if key in evaluation:
            tables[name] = evaluation[key]
    if recommendations is not None:
        tables["demo_recommendations.csv"] = recommendations
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        def write(name, data):
            archive.writestr("Results/"+name, data)
        for name, frame in tables.items():
            write(name, frame.to_csv(index=False).encode("utf-8-sig"))
        for name, obj in [("run_summary.json", summary), ("cleaning_audit.json", dataset.audit),
                          ("environment_versions.json", versions)]:
            write(name, json.dumps(obj, indent=2))
        text = io.StringIO(newline="")
        csv.writer(text).writerows(dataset.baskets)
        write("cleaned_baskets.csv", text.getvalue())
        write("dataset_source.txt", f"Case-study source: {SOURCE}\nUploaded CSV SHA-256: {dataset.sha256}\nA matching shape does not prove identical dataset contents.\n")
        figures = list(zip(["01_product_frequency", "02_basket_sizes"], overview_figures(result)))
        lift, scatter = rule_figures(result)
        if lift is not None:
            figures.extend([("03_rule_lift", lift), ("04_support_confidence", scatter)])
        figures.append(("05_pair_support", pair_figure(result)))
        figures.append(("06_itemset_sizes", itemset_size_figure(result)))
        if recommendations is not None and not recommendations.empty:
            figures.append(("07_recommendations", recommendation_figure(recommendations)))
        for name, fig in figures:
            # Embedded plotly.js keeps downloaded HTML usable without internet.
            write(name+".html", fig.to_html(include_plotlyjs=True, full_html=True))
        # Matplotlib PNGs avoid an extra browser/Kaleido dependency for screenshots.
        with plt.rc_context({"text.color": "black", "axes.labelcolor": "black", "axes.edgecolor": "black",
                             "figure.facecolor": "white", "axes.facecolor": "white", "font.size": 11}):
            freq = result["frequencies"].head(10).iloc[::-1]
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(freq["Product"], freq["Support (%)"], color="white", edgecolor="black", hatch="//")
            ax.set(xlabel="Baskets containing product (%)", title="Most frequent product categories")
            fig.tight_layout()
            image = io.BytesIO(); fig.savefig(image, format="png", dpi=160); plt.close(fig)
            write("01_product_frequency.png", image.getvalue())
            view = rule_view(result["rules"], n)
            fig, ax = plt.subplots(figsize=(9, 6))
            if not view.empty:
                ax.scatter(view["Support (%)"], view["Confidence (%)"], facecolors="none", edgecolors="black")
            else:
                ax.text(.5, .5, "No rules at these thresholds", ha="center", transform=ax.transAxes)
            ax.set(xlabel="Support (%)", ylabel="Confidence (%)", title="Association-rule evidence")
            fig.tight_layout(); image = io.BytesIO(); fig.savefig(image, format="png", dpi=160); plt.close(fig)
            write("02_support_confidence.png", image.getvalue())
        write("README.md", f"""# Current UI run results

These files were computed from the uploaded dataset, not copied from a reference run.

- Baskets: {n:,}; categories: {len(result['matrix'].columns)}.
- Minimum support: {result['support']:.2%}; minimum confidence: {result['confidence']:.2%}.
- Maximum itemset length: {result['max_len'] or 'unrestricted'}.
- Frequent itemsets: {len(result['itemsets'])}; baseline rules: {len(result['rules'])}; positive rules: {len(result['positive_rules'])}.
- Independent rule checks: {result['verified_rules']}.
- Evaluation exports appear only for experiments you ran in the Evaluation section.
- A recommendation CSV appears only after you generated recommendations.

Open HTML charts in a browser; JavaScript is embedded for offline viewing. PNG charts can be placed in a report.
CSV support and confidence columns marked (%) are already percentages. Lift is a ratio.
Support counts describe complete product combinations. Predictions are not guaranteed customer purchases.
The hold-out screen, when present, is exploratory and is not classification accuracy.
No controlled commercial trial has been performed. Review profitability, stock and validation before a business pilot.
""")
    return output.getvalue()
