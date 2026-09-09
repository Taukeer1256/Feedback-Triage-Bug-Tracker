## Evaluation Results

Evaluated on 30 hand-labeled items (stratified sample from `eval_sample.csv`).

| Category | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| bug                  | 100.0% | 100.0% | 100.0% | 6 |
| feature_request      | 100.0% | 100.0% | 100.0% | 6 |
| noise                | 100.0% | 90.0% | 94.7% | 10 |
| ux_confusion         | 88.9% | 100.0% | 94.1% | 8 |
| **Macro average** | **97.2%** | **97.5%** | **97.2%** | — |

**Overall accuracy: 96.7%**

Model: `gemini-3.5-flash-lite` · Dedup threshold: `0.82`
