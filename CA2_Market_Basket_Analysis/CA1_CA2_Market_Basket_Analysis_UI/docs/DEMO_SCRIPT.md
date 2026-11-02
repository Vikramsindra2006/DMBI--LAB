# CA2 UI demonstration script

Suggested duration: 6–8 minutes. Use the included dataset and reference settings. Run setup and the tests before the presentation. Do not read every row or line of code aloud.

## Before the demonstration

1. Extract the project folder and install packages using SETUP_WINDOWS.bat.
2. Launch RUN_APP_WINDOWS.bat and keep its terminal open.
3. Confirm you can find Dataset/groceries.csv in the upload dialog.
4. Set support to 1%, confidence to 25% and maximum length to Unrestricted.
5. Keep the POC/PPT and your GitHub repository available separately.

## 1. Introduce the business problem

**Say:** “Our project is Market Basket Analysis for retail decision making. We want to identify products that customers buy together and use the evidence to demonstrate relevant basket suggestions. We implement Apriori and FP-Growth and evaluate the generated association rules.”

**Show:** The initial app page. Point out that no dataset is loaded until you select one.

## 2. Upload and explain the dataset

**Do:** Upload Dataset/groceries.csv. Stay on Upload & overview.

**Say:** “This is the Kaggle Groceries basket dataset. Each row is one shopping transaction. It contains 9,835 baskets and 169 product categories. It has product presence, but it does not give us transaction prices, quantities or profit.”

**Show:** Basket preview, frequencies and the basket-size chart.

**Say:** “Before mining, we standardize product names, remove blank tokens and ensure one category is counted once within a basket. We retain identical baskets across separate rows because they may represent different purchases. The audit reports what actually happened.”

## 3. Run and explain the algorithms

**Do:** Select Mine patterns and click Run analysis.

**Say:** “The data becomes a Boolean matrix: one row per basket and one column per product. Apriori generates candidates and prunes them when a subset is infrequent. FP-Growth uses a compressed pattern structure. Both receive the same data and thresholds.”

**Say:** “Our minimum support is 1%, so a combination must occur in at least 99 baskets. Minimum confidence is 25%. The current run finds 333 frequent itemsets and 170 rules. There are 169 rules with positive lift. The application checks that both algorithms agree and recalculates the rule metrics directly from basket counts.”

Explain that timings change by machine. Do not promise FP-Growth will always be faster.

## 4. Interpret one rule

**Do:** Open Explore rules and explain the leading produce rule.

**Say:** “Citrus fruit and other vegetables imply root vegetables as an association rule. The complete combination occurs in 102 baskets, giving about 1.04% support. Among baskets containing the antecedent, about 35.92% also contain root vegetables. Its lift of about 3.30 means that this conditional frequency is 3.30 times the overall frequency of root vegetables.”

**Say:** “Lift is not a predicted sales increase. The rule describes historical association. We still need a business trial to know whether an intervention improves profit.”

**Show:** Search, the lift chart, the support/confidence scatter and selected pair support. Hover on a mark to see its evidence.

## 5. Demonstrate a basket recommendation

**Do:** Open Basket recommendations. Select curd and whole milk, then click Suggest products.

**Say:** “The recommender looks for rules whose entire antecedent is present in our basket. It excludes products already selected. Here, yogurt is suggested through the curd-and-milk rule, and other vegetables match a shorter curd rule. Each suggestion shows its support count, confidence and lift.”

**Do:** Add yogurt and click Suggest products again. Explain that yogurt is no longer suggested because it is already in the basket. Return to the original basket if you want to export that example.

## 6. Evaluate stability

**Do:** Open Evaluation and run the hold-out experiment. Optionally run the benchmark and sensitivity experiment.

**Say:** “We separate discovery and validation baskets before mining the shortlisted rules. With seed 42, there are 7,868 discovery baskets and 1,967 validation baskets. Eight of ten shortlisted rules pass our exploratory conditions.”

**Say:** “The yogurt rule has 19 joint validation baskets and narrowly fails the minimum of 20, even though its confidence and lift remain positive. The recommender shows matching logic, but this particular rule is not fully accepted under our validation policy. This is why we inspect counts and stability, rather than selecting rules using lift alone.”

**If showing sensitivity:** “Changing thresholds changes how many patterns qualify. No rules at a stricter threshold is a valid result, not a program failure.”

## 7. Export and conclude

Before exporting, optionally open **Live charts** and adjust confidence to show an immediate graph update. Open **Live stream (simulation)**, click Start replay and explain that uploaded baskets are being replayed in CSV order. Pause, advance one batch and reset. Call this a simulation, because it is not a live retailer feed. The full-data association results remain unchanged.

**Do:** Open Download results, click Prepare results ZIP and download it.

**Say:** “The export contains the actual current tables, settings, audit records and charts. Evaluation files appear only for the experiments we ran. We can place these results in GitHub as evidence.”

**Conclude:** “The project demonstrates the complete path from uploaded data to evaluated associations and explainable recommendations. A retailer can use this evidence to shortlist a controlled pilot, after checking stock and margins. We do not claim that this prototype has already increased sales.”

## Likely viva questions

**Why is this unsupervised?** There is no predefined class label. We discover co-occurrence patterns.

**What does Apriori calculate first?** Counts and supports for product combinations, retaining those meeting minimum support. Rules are generated afterward.

**Does high confidence always mean a useful rule?** No. A popular consequent can produce high confidence. Lift compares against that baseline popularity.

**Why use both algorithms?** They offer different search strategies, let us compare runtime and independently confirm equivalent itemsets and supports.

**What if no rule matches a basket?** Return no suggestion. Do not invent a recommendation.

**Why keep repeated baskets?** Equal contents do not prove duplicate transaction events.

**Is the hold-out pass rate model accuracy?** No. It is the fraction of a selected rule shortlist meeting an exploratory stability screen.

**Is the UI the algorithm?** No. Streamlit collects inputs and displays outputs. The Python analysis module performs mining and evaluation.

**Does this use ADWIN?** No. ADWIN is the separate CA3 presentation topic. This CA2 implements market basket association mining.
