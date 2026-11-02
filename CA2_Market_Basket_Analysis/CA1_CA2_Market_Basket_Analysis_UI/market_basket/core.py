"""Upload parsing, preprocessing, association mining and evaluation.

No Streamlit dependencies here: the same functions run from the UI or tests.
All metrics use proportions internally. Display functions convert to percentages.
"""
from __future__ import annotations

import csv
import hashlib
import inspect
import io
import math
import time
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules, fpgrowth
from mlxtend.preprocessing import TransactionEncoder

SOURCE = "https://www.kaggle.com/datasets/irfanasrullah/groceries"
MAX_BYTES = 20 * 1024 * 1024
RULE_COLUMNS = ["antecedents", "consequents", "antecedent support",
                "consequent support", "support", "confidence", "lift"]
RECOMMENDATION_COLUMNS = ["Product", "Matched antecedent", "Joint baskets", "Confidence (%)", "Lift"]


@dataclass
class Dataset:
    baskets: list[list[str]]
    audit: dict
    filename: str
    sha256: str
    input_format: str
    canonical_shape: bool


def clean_baskets(records):
    """Normalize labels and presence within baskets; keep repeated shopping events."""
    audit = Counter(raw_baskets=len(records))
    cleaned = []
    for row in records:
        items = []
        for token in row:
            normal = token.strip().lower()
            audit["tokens_normalised"] += int(token != normal)
            if normal:
                items.append(normal)
            else:
                audit["empty_tokens_removed"] += 1
        unique = list(dict.fromkeys(items))
        audit["within_basket_repeats_removed"] += len(items) - len(unique)
        if unique:
            cleaned.append(unique)
        else:
            audit["empty_baskets_excluded"] += 1
    audit["retained_baskets"] = len(cleaned)
    audit["distinct_categories"] = len({x for b in cleaned for x in b})
    audit["repeated_basket_contents_retained"] = len(cleaned) - len({tuple(sorted(b)) for b in cleaned})
    keys = ["raw_baskets", "tokens_normalised", "empty_tokens_removed",
            "within_basket_repeats_removed", "empty_baskets_excluded", "retained_baskets",
            "distinct_categories", "repeated_basket_contents_retained"]
    return cleaned, {k: int(audit[k]) for k in keys}


def load_upload(payload: bytes, filename: str, strict: bool = True) -> Dataset:
    """Read only the explicitly uploaded bytes. ZIP members are never extracted."""
    if not payload:
        raise ValueError("The selected file is empty. Upload your groceries CSV or ZIP.")
    if len(payload) > MAX_BYTES:
        raise ValueError("Please choose a file smaller than 20 MB.")
    if not filename.lower().endswith((".csv", ".zip")):
        raise ValueError("Choose a CSV or ZIP file.")
    if filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = [m for m in archive.infolist() if not m.is_dir()
                           and m.filename.lower().endswith(".csv")
                           and "__MACOSX" not in m.filename.split("/")]
                preferred = [m for m in members if PurePosixPath(m.filename).name.lower() == "groceries.csv"]
                choices = preferred if len(preferred) == 1 else members
                if len(choices) != 1:
                    raise ValueError("The ZIP must contain one CSV or one clearly named groceries.csv. Otherwise upload the desired CSV directly.")
                member = choices[0]
                if member.file_size > MAX_BYTES:
                    raise ValueError("The CSV inside this ZIP exceeds the 20 MB limit.")
                filename = f"{filename} :: {member.filename}"
                with archive.open(member) as stream:
                    payload = stream.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise ValueError("The expanded CSV exceeds 20 MB.")
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as exc:
            raise ValueError("This ZIP cannot be opened. Upload an unencrypted CSV or ZIP.") from exc
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Save the dataset as a UTF-8 CSV and upload it again.") from exc
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise ValueError("The CSV contains malformed quoting. Upload the original Kaggle file.") from exc
    if not rows or not any(any(t.strip() for t in row) for row in rows):
        raise ValueError("The CSV does not contain any products.")
    # Ignore leading blank lines without consuming the first actual basket.
    while rows and not any(t.strip() for t in rows[0]):
        rows.pop(0)
    header = [t.strip().lower() for t in rows[0]]
    if {"member_number", "date", "itemdescription"}.issubset(header):
        raise ValueError("This is the other Groceries dataset. Choose the 9,835-basket Kaggle dataset linked in the app.")
    if header[0] == "item(s)":
        records = []
        for number, row in enumerate(rows[1:], start=2):
            if not any(t.strip() for t in row):
                records.append([])
                continue
            try:
                expected = int(row[0].strip())
            except ValueError as exc:
                raise ValueError(f"Invalid item count on CSV row {number}.") from exc
            actual = [x for x in row[1:] if x.strip()]
            if expected != len(actual):
                raise ValueError(f"CSV row {number} declares {expected} products but contains {len(actual)}. Use the original download.")
            records.append(actual)
        format_name = "Wide CSV with Item(s) count and padding"
    else:
        records = rows
        format_name = "Headerless CSV, one basket per row"
    baskets, audit = clean_baskets(records)
    n, k = len(baskets), audit["distinct_categories"]
    if not n or k < 2:
        raise ValueError("At least one nonempty basket and two different product categories are required.")
    if n > 20000 or k > 500:
        raise ValueError("This classroom app supports up to 20,000 baskets and 500 categories.")
    canonical = n == 9835 and k == 169
    if strict and not canonical:
        raise ValueError(f"Found {n:,} baskets and {k} categories. The case-study dataset has 9,835 baskets and 169 categories. Upload that file, or turn off the case-study shape check for your own basket CSV.")
    return Dataset(baskets, audit, filename, hashlib.sha256(payload).hexdigest(), format_name, canonical)


def encode(baskets):
    encoder = TransactionEncoder()
    matrix = encoder.fit(baskets).transform(baskets)
    return pd.DataFrame(matrix, columns=encoder.columns_, dtype=bool)


def mine(matrix, min_support, algorithm="Apriori", max_len=None):
    if not 0 < min_support <= 1:
        raise ValueError("Minimum support must be greater than 0 and at most 1.")
    if algorithm not in ("Apriori", "FP-Growth"):
        raise ValueError("Choose Apriori or FP-Growth.")
    if max_len is not None and (not isinstance(max_len, int) or max_len < 1):
        raise ValueError("Maximum itemset length must be a positive integer.")
    func = apriori if algorithm == "Apriori" else fpgrowth
    start = time.perf_counter()
    result = func(matrix, min_support=min_support, use_colnames=True, max_len=max_len)
    elapsed = time.perf_counter() - start
    return result, elapsed


def generate_rules(itemsets, n, confidence):
    if not 0 <= confidence <= 1:
        raise ValueError("Confidence must be between 0 and 1.")
    if itemsets.empty or not itemsets["itemsets"].map(len).ge(2).any():
        return pd.DataFrame(columns=RULE_COLUMNS)
    kwargs = {"metric": "confidence", "min_threshold": confidence}
    signature = inspect.signature(association_rules).parameters
    if "num_itemsets" in signature:
        kwargs["num_itemsets"] = n
    if "return_metrics" in signature:
        kwargs["return_metrics"] = ["antecedent support", "consequent support", "support", "confidence", "lift"]
    rules = association_rules(itemsets, **kwargs)[RULE_COLUMNS]
    return rules.sort_values(["lift", "confidence", "support"], ascending=False).reset_index(drop=True)


def agree(first, second):
    a = dict(zip(first.itemsets, first.support))
    b = dict(zip(second.itemsets, second.support))
    return a.keys() == b.keys() and all(np.isclose(a[k], b[k], rtol=1e-10, atol=1e-12) for k in a)


def rule_view(rules, n):
    cols = ["Antecedent", "Consequent", "Joint baskets", "Support (%)", "Confidence (%)", "Lift"]
    return pd.DataFrame([{
        "Antecedent": " + ".join(sorted(r.antecedents)),
        "Consequent": " + ".join(sorted(r.consequents)),
        "Joint baskets": int(round(r.support * n)), "Support (%)": r.support * 100,
        "Confidence (%)": r.confidence * 100, "Lift": r.lift,
    } for r in rules.itertuples(index=False)], columns=cols)


def itemset_view(itemsets, n):
    return pd.DataFrame([{"Products": " + ".join(sorted(r.itemsets)), "Size": len(r.itemsets),
                          "Joint baskets": int(round(r.support*n)), "Support (%)": r.support*100}
                         for r in itemsets.itertuples(index=False)],
                        columns=["Products", "Size", "Joint baskets", "Support (%)"])


def frequencies(matrix):
    counts = matrix.sum().astype(int).sort_values(ascending=False)
    return pd.DataFrame({"Product": counts.index, "Baskets": counts.values,
                         "Support (%)": counts.values / len(matrix) * 100})


def check_metrics(matrix, rules):
    """Recalculate every rule from Boolean basket counts, independent of mlxtend."""
    for r in rules.itertuples(index=False):
        a = matrix[list(r.antecedents)].all(axis=1)
        b = matrix[list(r.consequents)].all(axis=1)
        joint = float((a & b).mean())
        expected = [joint, joint / a.mean(), joint / a.mean() / b.mean()]
        if not np.allclose(expected, [r.support, r.confidence, r.lift], rtol=1e-9, atol=1e-12):
            raise ValueError("A rule failed the independent count check. Analysis stopped.")
    return len(rules)


def run_analysis(dataset, support=.01, confidence=.25, max_len=None):
    matrix = encode(dataset.baskets)
    first, ta = mine(matrix, support, "Apriori", max_len)
    second, tf = mine(matrix, support, "FP-Growth", max_len)
    equivalent = agree(first, second)
    if not equivalent:
        raise ValueError("The algorithms produced different itemsets. Please review the dataset and configuration.")
    rules = generate_rules(second, len(matrix), confidence)
    verified = check_metrics(matrix, rules)
    return {"matrix": matrix, "itemsets": second, "rules": rules,
            "positive_rules": rules[rules.lift > 1].copy(),
            "frequencies": frequencies(matrix), "equivalent": equivalent,
            "verified_rules": verified,
            "timings": pd.DataFrame({"Algorithm": ["Apriori", "FP-Growth"],
                                     "Seconds": [ta, tf], "Itemsets": [len(first), len(second)]}),
            "support": support, "confidence": confidence, "max_len": max_len}


def recommend(items, rules, matrix, min_lift=1., limit=5):
    selected = {str(x).strip().lower() for x in items if str(x).strip()}
    if not selected:
        raise ValueError("Select at least one product.")
    unknown = selected - set(matrix.columns)
    if unknown:
        raise ValueError("Unknown products: " + ", ".join(sorted(unknown)))
    result = []
    for r in rules.itertuples(index=False):
        if len(r.consequents) != 1 or not r.antecedents.issubset(selected) or r.lift <= min_lift:
            continue
        item = next(iter(r.consequents))
        if item not in selected:
            result.append({"Product": item, "Matched antecedent": " + ".join(sorted(r.antecedents)),
                           "Joint baskets": int(round(r.support*len(matrix))),
                           "Confidence (%)": r.confidence*100, "Lift": r.lift})
    frame = pd.DataFrame(result, columns=RECOMMENDATION_COLUMNS)
    if frame.empty:
        return frame
    return (frame.sort_values(["Lift", "Confidence (%)", "Joint baskets", "Product"],
                             ascending=[False, False, False, True])
            .drop_duplicates("Product").head(limit).reset_index(drop=True))


def holdout(matrix, support, confidence, max_len=None, seed=42, limit=10):
    """Mine on discovery baskets only; score the shortlist on untouched validation baskets."""
    if len(matrix) < 20:
        raise ValueError("Use at least 20 baskets for the discovery/validation experiment.")
    order = np.random.default_rng(seed).permutation(len(matrix))
    cutoff = int(.8*len(matrix))
    discovery, validation = matrix.iloc[order[:cutoff]], matrix.iloc[order[cutoff:]]
    itemsets, _ = mine(discovery, support, "FP-Growth", max_len)
    rules = generate_rules(itemsets, len(discovery), confidence)
    rules = rules[(rules.lift > 1) & rules.consequents.map(len).eq(1)].head(limit)
    out = []
    min_count = math.ceil(support*len(validation)-1e-12)
    for r in rules.itertuples(index=False):
        a = validation[list(r.antecedents)].all(axis=1)
        b = validation[list(r.consequents)].all(axis=1)
        count, acount, bcount = int((a & b).sum()), int(a.sum()), int(b.sum())
        conf = count / acount if acount else 0.
        lift = conf / (bcount/len(validation)) if bcount else 0.
        out.append({"Rule": " + ".join(sorted(r.antecedents))+" → "+" + ".join(sorted(r.consequents)),
                    "Discovery lift": r.lift, "Validation lift": lift,
                    "Validation joint count": count, "Validation confidence (%)": conf*100,
                    "Pass": bool(lift > 1 and conf >= confidence and count >= min_count)})
    columns = ["Rule", "Discovery lift", "Validation lift", "Validation joint count", "Validation confidence (%)", "Pass"]
    return pd.DataFrame(out, columns=columns), {"discovery_baskets": len(discovery),
            "validation_baskets": len(validation), "seed": seed, "minimum_joint_count": min_count,
            "min_support": support, "min_confidence": confidence, "min_lift_exclusive": 1.0}


def benchmark(matrix, support, max_len=None, repeats=3):
    rows = []
    for name in ("Apriori", "FP-Growth"):
        times = [mine(matrix, support, name, max_len)[1] for _ in range(repeats)]
        rows.append({"Algorithm": name, "Median seconds": float(np.median(times)),
                     "Minimum seconds": min(times), "Maximum seconds": max(times), "Repetitions": repeats})
    return pd.DataFrame(rows)


def sensitivity(matrix, max_len=None):
    rows = []
    for support in (.005, .01, .02):
        itemsets, _ = mine(matrix, support, "FP-Growth", max_len)
        for confidence in (.25, .4, .6):
            rules = generate_rules(itemsets, len(matrix), confidence)
            rows.append({"Support (%)": support*100, "Confidence (%)": confidence*100,
                         "Itemsets": len(itemsets), "Rules": len(rules),
                         "Positive rules": int((rules.lift > 1).sum())})
    return pd.DataFrame(rows)
