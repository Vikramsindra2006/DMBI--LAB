# Dataset

`groceries.csv` is the headerless basket CSV used in the earlier verified CA2 implementation.

- Source: https://www.kaggle.com/datasets/irfanasrullah/groceries
- Documentation: https://michael.hahsler.net/arules/reference/Groceries.html
- 9,835 transactions and 169 product categories after normalization.
- SHA-256: `9f6ff7186d88eebe08904798a21d477a2cff475ae145f993e80db80ef567dfeb`

Each row is one basket, containing comma-separated product categories. Rows may have different lengths.
There is no target class, price, quantity, customer ID or timestamp in this representation.

**The app does not read this file automatically.** Select it using the sidebar uploader.
You can instead upload your downloaded Kaggle CSV, the wide Item(s) version, or a ZIP containing the CSV.
The different Member_number / Date / itemDescription dataset is not the input for this case study.

Keep the original dataset attribution and check the source's reuse terms before redistributing the data beyond your course submission.
