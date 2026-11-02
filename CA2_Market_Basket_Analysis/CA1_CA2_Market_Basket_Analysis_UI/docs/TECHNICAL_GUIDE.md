# Implementation explanation

## Architecture

`app.py` handles the browser interface. `market_basket/core.py` contains analysis functions independent of Streamlit. `charts.py` creates Plotly figures. `exports.py` builds evidence archives in memory. Tests can exercise the analytical module without a running server.

## Upload and preprocessing

`load_upload(payload, filename, strict)` accepts the bytes from the explicit upload widget. It validates the extension and byte limits. ZIP handling reads a chosen CSV member without extracting it. Ambiguous archives receive a message asking the user to select the desired CSV directly.

The parser uses Python's CSV reader, rather than rectangular DataFrame import, because basket rows have different lengths. It preserves the first headerless basket. For wide files, it recognizes Item(s), removes count and padding columns and checks the declared count. The incompatible member/date/item dataset receives an explanatory rejection.

`clean_baskets(records)` trims whitespace, lowercases labels, counts changes, removes blank tokens and deduplicates categories within a basket. It preserves separate rows with equal contents. The default shape check expects the canonical case study but can be disabled for another correctly formatted dataset. Shape checks do not establish dataset identity; SHA-256 records exact input bytes.

`encode(baskets)` calls TransactionEncoder and returns a Boolean DataFrame. Boolean data is the appropriate input for mlxtend and avoids the warning produced by deprecated non-Boolean input paths.

## Frequent patterns and association rules

`mine(matrix, min_support, algorithm, max_len)` calls Apriori or FP-Growth with equal support and length settings. It times only that call. The input uses proportions: 0.01 is 1%, not 0.01%.

`agree(first, second)` compares unordered itemset identities and floating-point support values with a numerical tolerance. Matching only the number of itemsets would not be enough.

`generate_rules(itemsets, n, confidence)` checks for a nonempty frequent itemset table and at least one itemset of length two. It then calls mlxtend association_rules. A function-signature check supplies num_itemsets when supported. Requested metrics avoid calculating unused division-sensitive measures such as conviction. Empty itemsets or a lack of qualifying rules returns an empty table with a known schema.

`check_metrics(matrix, rules)` independently computes antecedent presence, consequent presence and joint presence for every rule. It recalculates support, confidence and lift and rejects inconsistent results. This verifies the mining output against actual basket membership.

`run_analysis(...)` orchestrates encoding, both miners, agreement checks, rule generation and direct verification. Its result object contains the exact data, settings, metrics and timings for the current run.

## Recommendations

`recommend(items, rules, matrix, min_lift, limit)` validates the basket, requires every antecedent product, keeps single-product consequents and excludes products already present. It filters by positive lift, ranks the matches and retains the strongest explanation per suggested product. It returns an empty table when no rule matches. No generative model or fabricated fallback is used.

The current rule set already meets the confidence selected during mining. The recommendation lift control applies an additional strict lower bound: the rule's lift must exceed the chosen value.

## Evaluation

`benchmark` repeats mining three times and reports median, minimum and maximum duration. Encoding and rule generation are outside these timings.

`sensitivity` mines at each support once, then generates rules for each confidence. It evaluates the nine configured threshold pairs while preserving the current maximum length restriction.

`holdout` uses a NumPy seed-42 permutation and an 80/20 split. It mines rules using discovery baskets only, selects up to ten positive single-consequent rules and recalculates their confidence, lift and joint counts on validation baskets. Its screen uses the configured support and confidence, plus lift strictly above 1. This is an exploratory rule-stability experiment, not a trained classifier accuracy calculation or a business-impact test.

## State and exports

The uploader signature includes a hash of the selected bytes, filename and validation mode. The analysis signature includes the parsed CSV hash and mining parameters. A changed dataset or setting clears the previous run, evaluation and prepared archive.

Recommendations have their own basket/threshold/limit signature. If those controls change, an older recommendation is not exported as current. Newly completed evaluation experiments invalidate an earlier prepared ZIP.

`build_export` builds a ZIP entirely in memory. CSVs have readable product strings instead of Python frozensets. The run summary records current parameters, upload fingerprint, counts and completed evaluations. Interactive HTML charts embed Plotly JavaScript for offline viewing. Matplotlib generates PNGs without Kaleido or Chrome. No packages are installed automatically during app execution.

The optional local-save button writes only exporter-created filenames under this project's Results folder. The ZIP is outside the individual run directory, so it cannot include itself. The original uploaded dataset is never overwritten.

## Dynamic chart and replay implementation

The Live charts controls filter the existing rule table, then rebuild the lift and scatter figures. They do not silently mine at thresholds below the configured analysis. `recommendation_figure` follows the current automatically recalculated suggestion table. `itemset_size_figure` counts the sizes of actual mined itemsets.

`market_basket/live.py` implements `advance_cursor` and `replay_snapshot`. The latter takes the processed prefix of the Boolean matrix and uses cumulative counts to calculate product and pair support. It calculates confidence and lift for the prefix and returns undefined values when the relevant denominators are zero. History points include a final partial batch. Counts at the end match full-data counts exactly.

The replay UI uses a Streamlit fragment. Its `run_every` interval is active only while replay is running. A monotonic-time check limits processing to one batch per due update. Start, Pause, Reset and Next batch update session state through callbacks. Leaving the replay page pauses the stream. The end-of-file condition disables the repeating schedule. No sleeping loop, random incoming transaction generation or frequent-pattern remine occurs during each tick.

The title renders before scientific imports, a spinner reports loading progress, and matplotlib/export imports are deferred until export preparation. This makes startup work visible without asserting that the user's earlier blank screen had a proven cause.

## Scope and limits

The local app requires no account, database or API key. It processes the selected file and exposes no model-serving or order-execution functionality. It is a classroom prototype with input-size limits, not a scalable retail production system. Association metrics do not prove causation, profitability or future customer behavior.
