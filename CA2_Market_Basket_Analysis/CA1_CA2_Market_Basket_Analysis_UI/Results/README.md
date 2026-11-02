# Results

The UI generates current results rather than loading precomputed metrics.

1. Upload the dataset and run the analysis.
2. Run the optional benchmark, sensitivity and hold-out experiments.
3. Generate a recommendation if you want it included in the export.
4. Open Download results, select Prepare results ZIP, then download it.
5. Extract its `Results/` folder and commit those files to your submission repository.

The optional Save a copy button writes into `Results/run_<UTC timestamp>/` and places the ZIP beside that directory.
Downloaded HTML charts contain embedded JavaScript and can be viewed offline. PNG charts are available for reports.
Evaluation files appear only when their experiments have run. Timings are measured on the current machine.

The `.gitignore` excludes newly saved local runs by default. To submit them deliberately, either copy the exported files directly into this Results folder or use `git add -f Results/run_20261102T120000_000000Z`.
