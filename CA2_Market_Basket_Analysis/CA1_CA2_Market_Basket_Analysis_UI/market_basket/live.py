"""Exact metrics for replaying a static upload, never fabricated live sales."""
import numpy as np
import pandas as pd


def advance_cursor(cursor, batch_size, total):
    if batch_size < 1 or total < 0 or cursor < 0:
        raise ValueError("Replay sizes must be non-negative, and batch size must be positive.")
    return min(cursor + batch_size, total)


def replay_snapshot(matrix, cursor, product_a, product_b, batch_size=100, top_n=10):
    """Recompute exact cumulative category and pair support for a processed prefix."""
    if product_a == product_b or product_a not in matrix or product_b not in matrix:
        raise ValueError("Choose two different products from the uploaded data.")
    if not 0 < cursor <= len(matrix) or batch_size < 1:
        raise ValueError("Process a batch before requesting replay metrics.")
    prefix = matrix.iloc[:cursor]
    a, b = prefix[product_a].to_numpy(dtype=bool), prefix[product_b].to_numpy(dtype=bool)
    points = np.unique(np.r_[np.arange(batch_size, cursor+1, batch_size), cursor]).astype(int)
    history = pd.DataFrame({"Baskets processed": points,
        product_a: np.cumsum(a)[points-1] / points * 100,
        product_b: np.cumsum(b)[points-1] / points * 100,
        "Both products": np.cumsum(a & b)[points-1] / points * 100})
    counts = prefix.sum().astype(int).sort_values(ascending=False).head(top_n)
    ranking = pd.DataFrame({"Product": counts.index, "Baskets": counts.values,
                            "Support (%)": counts.values / cursor * 100})
    acount, bcount, joint = int(a.sum()), int(b.sum()), int((a & b).sum())
    confidence = joint/acount if acount else None
    lift = confidence/(bcount/cursor) if acount and bcount else None
    metrics = {"baskets": cursor, "joint_baskets": joint, "support": joint/cursor,
               "confidence": confidence, "lift": lift}
    return history, ranking, metrics
