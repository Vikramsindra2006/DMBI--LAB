import numpy as np
import pytest

from market_basket.core import encode, recommend
from market_basket.live import advance_cursor, replay_snapshot
from market_basket.charts import replay_figures, recommendation_figure, itemset_size_figure, rule_figures


def test_replay_exact_prefix_counts_and_final_short_batch():
    x = encode([["a"], ["a", "b"], ["b"], ["a", "b"], ["a"]])
    h, rank, m = replay_snapshot(x, 4, "a", "b", batch_size=2)
    assert h["Baskets processed"].tolist() == [2, 4]
    assert h.a.tolist() == [100., 75.]
    assert h.b.tolist() == [50., 75.]
    assert h["Both products"].tolist() == [50., 50.]
    assert m["support"] == .5 and m["joint_baskets"] == 2
    assert m["confidence"] == pytest.approx(2/3)
    assert m["lift"] == pytest.approx(8/9)
    assert advance_cursor(4, 2, 5) == 5
    h, _, _ = replay_snapshot(x, 5, "a", "b", batch_size=2)
    assert h["Baskets processed"].tolist() == [2, 4, 5]
    assert rank.Baskets.tolist() == [3, 3]


def test_replay_absent_antecedent_is_undefined():
    x = encode([["b"], ["a", "b"]])
    _, _, m = replay_snapshot(x, 1, "a", "b")
    assert m["support"] == 0
    assert m["confidence"] is None and m["lift"] is None
    with pytest.raises(ValueError):
        replay_snapshot(x, 1, "a", "a")


def test_full_replay_equals_full_data_counts(analysis):
    x = analysis["matrix"]
    history, ranking, metrics = replay_snapshot(x, len(x), "whole milk", "other vegetables", 100)
    assert history["Baskets processed"].iloc[-1] == 9835
    assert metrics["joint_baskets"] == int((x["whole milk"] & x["other vegetables"]).sum())
    assert metrics["support"] == pytest.approx((x["whole milk"] & x["other vegetables"]).mean())
    trend, bars = replay_figures(history, ranking, "whole milk", "other vegetables")
    assert len(trend.data) == 3 and len(bars.data) == 1
    assert len(trend.data[0].x) == len(history)


def test_filtered_charts_use_filtered_data(analysis):
    high = analysis["rules"][analysis["rules"].confidence >= .5]
    first, second = rule_figures(analysis, high)
    assert first is not None
    assert len(second.data[0].x) == len(high)
    assert rule_figures(analysis, high.iloc[:0]) == (None, None)
    chart = itemset_size_figure(analysis)
    assert sum(chart.data[0].y) == 333
    r = recommend(["curd", "whole milk"], analysis["rules"], analysis["matrix"])
    rec = recommendation_figure(r)
    assert set(rec.data[0].y) == {"yogurt", "other vegetables"}
