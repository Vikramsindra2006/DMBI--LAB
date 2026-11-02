import csv
import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from market_basket.core import (RULE_COLUMNS, agree, benchmark, check_metrics, clean_baskets,
                               encode, generate_rules, holdout, load_upload, mine, recommend,
                               rule_view, sensitivity)
from market_basket.exports import build_export


def test_real_dataset_and_baseline(groceries, analysis):
    assert len(groceries.baskets) == 9835
    assert groceries.audit["distinct_categories"] == 169
    assert groceries.audit["tokens_normalised"] == 408
    assert groceries.audit["repeated_basket_contents_retained"] == 2824
    assert analysis["matrix"].shape == (9835, 169)
    assert len(analysis["itemsets"]) == 333
    assert len(analysis["rules"]) == 170
    assert len(analysis["positive_rules"]) == 169
    assert analysis["equivalent"]
    assert analysis["verified_rules"] == 170
    top = rule_view(analysis["rules"], 9835).iloc[0]
    assert top["Joint baskets"] == 102
    assert top.Lift == pytest.approx(3.295045459323103)


def test_cleaning_preserves_separate_baskets():
    rows, audit = clean_baskets([[" Milk ", "milk", ""], ["milk"], []])
    assert rows == [["milk"], ["milk"]]
    assert audit["tokens_normalised"] == 1
    assert audit["within_basket_repeats_removed"] == 1
    assert audit["repeated_basket_contents_retained"] == 1
    assert audit["empty_baskets_excluded"] == 1


def test_headerless_upload_keeps_first_basket():
    d = load_upload(b'bread,milk\nmilk,eggs\n', "renamed.csv", strict=False)
    assert d.baskets == [["bread", "milk"], ["milk", "eggs"]]


def test_wide_upload():
    d = load_upload(b'Item(s),Item 1,Item 2,Item 3\n2,milk,bread,\n1,eggs,,\n', "groceries - groceries.csv", False)
    assert d.baskets == [["milk", "bread"], ["eggs"]]


def test_wide_count_mismatch():
    with pytest.raises(ValueError, match="declares"):
        load_upload(b'Item(s),Item 1,Item 2\n3,milk,bread\n', "wide.csv", False)


def test_zip_renamed_file():
    f = io.BytesIO()
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("nested/groceries.csv", "bread,milk\nmilk,eggs\n")
    assert len(load_upload(f.getvalue(), "archive.zip", False).baskets) == 2


def test_ambiguous_zip():
    f = io.BytesIO()
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("a.csv", "bread,milk")
        z.writestr("b.csv", "milk,eggs")
    with pytest.raises(ValueError, match="one CSV"):
        load_upload(f.getvalue(), "archive.zip", False)


@pytest.mark.parametrize("payload,name,message", [
    (b'', 'empty.csv', 'empty'),
    (b'   \n', 'empty.csv', 'does not contain'),
    (b'not a zip', 'broken.zip', 'cannot be opened'),
    (b'\xff\xff', 'wrong.csv', 'UTF-8'),
    (b'milk,bread', 'file.txt', 'CSV or ZIP'),
    (b'Member_number,Date,itemDescription\n1,1/1/2000,milk', 'other.csv', 'other Groceries'),
])
def test_invalid_uploads(payload, name, message):
    with pytest.raises(ValueError, match=message):
        load_upload(payload, name)


def test_case_shape_rejects_unrelated_csv():
    with pytest.raises(ValueError, match="9,835"):
        load_upload(b'milk,bread\neggs,milk', 'own.csv')


def test_no_rules_and_no_itemsets():
    x = encode([["bread"], ["milk"], ["eggs"]])
    f, _ = mine(x, .9)
    assert f.empty
    assert generate_rules(f, 3, .25).empty
    singleton, _ = mine(x, .1)
    assert generate_rules(singleton, 3, .25).empty


def test_confidence_one_has_no_runtime_warning():
    x = encode([["bread", "milk"], ["bread", "milk"], ["milk"]])
    f, _ = mine(x, .3)
    r = generate_rules(f, len(x), .2)
    assert r.confidence.max() == 1.
    assert check_metrics(x, r) == 2


def test_metric_tampering_is_caught(analysis):
    damaged = analysis["rules"].head(1).copy()
    damaged.loc[damaged.index[0], "lift"] += .5
    with pytest.raises(ValueError, match="independent count"):
        check_metrics(analysis["matrix"], damaged)


def test_recommendation_requires_full_antecedent_and_excludes_present_products():
    x = encode([["curd", "milk", "yogurt"], ["curd", "milk"], ["milk"]])
    r = pd.DataFrame([[frozenset(["curd", "milk"]), frozenset(["yogurt"]), 2/3, 1/3, 1/3, .5, 1.5]], columns=RULE_COLUMNS)
    assert recommend(["curd"], r, x).empty
    assert recommend(["curd", "milk"], r, x).Product.tolist() == ["yogurt"]
    assert recommend(["curd", "milk", "yogurt"], r, x).empty
    with pytest.raises(ValueError, match="Select"):
        recommend([], r, x)
    with pytest.raises(ValueError, match="Unknown"):
        recommend(["unknown"], r, x)


def test_actual_recommendation(analysis):
    r = recommend(["curd", "whole milk"], analysis["rules"], analysis["matrix"])
    assert r.Product.tolist() == ["yogurt", "other vegetables"]
    assert r["Joint baskets"].tolist() == [99, 169]


def test_discovery_only_holdout_reproduces_reference(analysis):
    frame, config = holdout(analysis["matrix"], .01, .25)
    assert config["discovery_baskets"] == 7868
    assert config["validation_baskets"] == 1967
    assert config["minimum_joint_count"] == 20
    assert len(frame) == 10 and frame.Pass.sum() == 8
    yogurt = frame[frame.Rule.eq("curd + whole milk → yogurt")].iloc[0]
    assert yogurt["Validation joint count"] == 19 and not yogurt.Pass


def test_sensitivity_and_benchmark(analysis):
    s = sensitivity(analysis["matrix"])
    assert len(s) == 9
    base = s[(s["Support (%)"] == 1) & (s["Confidence (%)"] == 25)].iloc[0]
    assert base.Itemsets == 333 and base.Rules == 170
    assert s[(s["Support (%)"] == 1) & (s["Confidence (%)"] == 60)].iloc[0].Rules == 0
    b = benchmark(analysis["matrix"], .01)
    assert (b.Repetitions == 3).all()
    assert (b["Minimum seconds"] <= b["Median seconds"]).all()
    assert (b["Median seconds"] <= b["Maximum seconds"]).all()


def test_export_is_current_self_contained_and_omits_unrun_evaluations(groceries, analysis):
    result = build_export(groceries, analysis)
    with zipfile.ZipFile(io.BytesIO(result)) as z:
        assert z.testzip() is None
        assert "Results/holdout_validation.csv" not in z.namelist()
        summary = json.loads(z.read("Results/run_summary.json"))
        assert summary["baseline_rules"] == 170
        assert len(list(csv.reader(io.StringIO(z.read("Results/cleaned_baskets.csv").decode())))) == 9835
        assert len(pd.read_csv(z.open("Results/all_association_rules.csv"))) == 170
        assert b"plotly.js" in z.read("Results/03_rule_lift.html")
        assert z.read("Results/01_product_frequency.png").startswith(b'\x89PNG')
        assert all(n.startswith("Results/") and ".." not in n for n in z.namelist())
