# Live and interactive graphs

## Upgrade an existing installation

Stop the old server with Ctrl+C. Extract the updated project ZIP. Copy the new `app.py`, `market_basket/` folder and documentation into the current project folder, replacing the old versions. Keep your existing `.venv/` folder. No extra packages are required for the graph update.

In CMD, from the project folder:

```bat
.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

Open http://127.0.0.1:8502. Upload the CSV again and run analysis. A visible title and package-loading message appear before the scientific imports complete. This makes startup progress visible, but does not establish the cause of an earlier blank screen.

If the page remains blank, stop the server and run this diagnostic from the same folder:

```bat
.venv\Scripts\python.exe -u check_startup.py
```

Send the last printed line and any traceback for diagnosis. Python 3.12 remains the tested version. The setup script now also accepts an existing Python 3.13 environment, so it no longer insists on an unavailable 3.12 launcher.

## Live charts page

1. Upload the dataset and run analysis.
2. Select **Live charts**.
3. Change **Number of top products**. The product-frequency graph updates immediately.
4. Increase **Display confidence at least (%)** or **Display lift greater than**. The qualifying-rule count, lift ranking and scatter plot update immediately.
5. Inspect the itemset-size graph to see how many frequent single products, pairs and larger combinations qualified.

These are instant **display filters**, applied to the current mined rules. They cannot recover rules excluded by the original mining thresholds. For a new mining configuration, change sidebar settings and run analysis again. The app avoids repeatedly mining on every small display adjustment.

## Automatic recommendation graph

Open **Basket recommendations**. Select curd and whole milk. The suggestions table and graph update when the basket, minimum lift or maximum suggestions changes. The Suggest products button remains available as an explicit refresh.

Switch the chart metric between confidence, lift and joint baskets. Add yogurt to the selected basket to show that it disappears from recommendations. Removing all products shows a clear prompt instead of an error.

## Live stream simulation

Open **Live stream (simulation)** after running analysis.

- Choose two different tracked products.
- Set **Baskets per update** and a refresh interval of 0.5, 1, 2 or 5 seconds.
- Click **Start replay**. The fragment processes successive batches and refreshes the charts while the page is open.
- Click **Pause replay** to hold the current position.
- Click **Next batch** while paused for a controlled demonstration.
- Click **Reset replay** to return to zero.
- Leaving the replay page pauses it. The replay stops at the end instead of looping or fabricating more records.

### What changes on screen

| Graph / metric | Meaning |
|---|---|
| Cumulative-support line chart | Share of processed baskets containing A, B, or both |
| Top-product bar chart | Most common categories in the processed prefix |
| Processed baskets | Actual uploaded rows processed so far |
| Pair support | Joint count / processed basket count |
| A → B confidence | Joint count / processed baskets containing A |
| A → B lift | Confidence / B's support in the processed prefix |

Confidence or lift can be undefined when no supporting antecedent/consequent has appeared. The UI explicitly displays that condition. Changing tracked products recalculates the chart for those products at the existing position, without restarting the uploaded data.

**This is a replay of a static uploaded dataset.** Its order is the CSV's file order, not a verified historical time sequence. There is no live retailer connection, real-time sales feed, timestamp-based seasonality analysis, or ADWIN detector. The replay computes exact prefix counts and does not continually rerun Apriori or FP-Growth. It does not alter the saved full-data mining results.

Download the replay snapshot CSV directly from this page. Its history is separate from the main Results ZIP. The main export uses the current full-data mining run, not the temporary replay position.

## Suggested 60-second explanation

“These graphs let us explore the evidence interactively. The display thresholds immediately filter the already-mined rules. The recommendation chart follows the selected basket. For the replay, we take the real uploaded baskets in small batches and update product frequencies and pair metrics. This demonstrates a dashboard that refreshes automatically, but the underlying source is static, so we label it as a simulation.”

## Implementation reference

Automatic refresh uses Streamlit fragments with a dynamic `run_every` interval. Start and pause control the schedule; there is no blocking sleep loop or full mining pass on each tick.

https://docs.streamlit.io/develop/tutorials/execution-flow/start-and-stop-fragment-auto-reruns
