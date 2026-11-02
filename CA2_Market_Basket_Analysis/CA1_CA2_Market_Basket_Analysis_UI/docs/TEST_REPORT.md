# Validation report

Recorded for the delivered UI project on 2 November 2026.

## Test environment

- Python 3.12.14, Linux.
- Streamlit 1.66.1, Plotly 7.1.0, mlxtend 0.25.0.
- pandas 3.1.0, NumPy 2.5.4, matplotlib 3.11.2.
- Full dependency snapshot: requirements-lock.txt.
- Package consistency check: no broken requirements.

## Automated result

**32 tests passed** in the full analytical and Streamlit AppTest suite. RuntimeWarning is configured as an error, rather than globally hidden. The expanded suite covers dynamic chart controls, automatic recommendation updates and replay actions. Six UI integration tests also run separately after the final replay changes.

| Area | Evidence checked |
|---|---|
| Real data baseline | 9,835 baskets, 169 categories, 333 itemsets, 170 rules, 169 positive rules |
| Preprocessing | Actual audit counts, within-basket deduplication, separate repeated baskets retained |
| Headerless input | First actual basket preserved |
| Wide input | Item count and padding excluded; mismatched declared counts rejected |
| ZIP input | Nested CSV accepted, ambiguous archive rejected |
| Invalid files | Empty content, bad ZIP, non-UTF-8, unsupported extension and incompatible dataset rejected |
| Empty mining results | No itemsets and no rules handled without an exception |
| Metric verification | All baseline metrics recalculated; a deliberately damaged metric rejected |
| Confidence 1 | Rule generation succeeds without an invalid-division runtime warning |
| Recommender | Complete antecedents required, already-selected products excluded, empty and unknown baskets rejected |
| Actual recommendations | Curd + whole milk produces yogurt and other vegetables with recorded basket counts |
| Hold-out | Discovery-only mining, seed 42, 7,868/1,967 split, 8/10 pass and yogurt's 19-count limitation reproduced |
| Thresholds | Nine sensitivity configurations and the valid zero-rule result at 1%/60% |
| Timing | Three repetitions and ordered min/median/max values |
| Export | Valid ZIP, current data, readable tables, offline HTML JavaScript and PNG signatures |
| UI | Upload-first landing, all navigation pages, analysis, recommendation, all evaluation buttons and ZIP preparation |
| Dynamic graphs | Display thresholds update rule graphs; recommendation changes update the graph and table |
| Replay | Exact prefix support, zero-denominator handling, complete-file equality and final partial batches |
| Replay controls | Start, Pause, Next batch, Reset, a simulated due tick and pausing when leaving the page |
| Stale state | Changed thresholds and replacement uploads invalidate previous analysis and exports |

## Reference metrics

- Leading rule: citrus fruit + other vegetables → root vegetables.
- Joint baskets: 102.
- Support: approximately 1.0371%.
- Confidence: approximately 35.9155%.
- Lift: approximately 3.2950.
- Curd + whole milk → yogurt: full-data joint count 99, confidence approximately 38.5214%, lift approximately 2.7614.
- Hold-out yogurt rule: 19 joint baskets, below the validation count floor of 20.

## Verification boundaries

Streamlit AppTest ran the application code with controlled uploaded-file responses. This validates widget workflows and state transitions but does not exercise the operating system's actual file picker or pixel-level browser layout. A Streamlit server started successfully and its HTTP health endpoint responded. A browser-based visual/download check could not run because the browser binary was unavailable and its download failed in the test environment.

Automatic timer calculations were exercised through AppTest with a due tick, not a real browser timer event. No browser visual or wall-clock animation check is claimed.

The Windows batch files are provided for the user's Windows machine, but they were not executed on Windows here. Installation requires internet and Python 3.12. Timings will differ on another machine. Optional local-save behavior uses a new timestamped folder to avoid mixing files from different runs.

No production deployment, live retailer trial or commercial uplift evaluation was performed.

## Reproduce the tests

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

On Linux/macOS, use `.venv/bin/python` instead.
