# Phase 2 Residual Analysis

Six diagnostic plots were generated from a bounded deterministic Random Forest validation/test sample under `reports/figures/phase2/`: residual histogram, prediction versus actual, residual versus prediction, residual versus time, daily error trend, and monthly error trend. Positive residual means overprediction. Daily/monthly plots are sample diagnostics; the metrics below use the complete partitions.

## Calculated findings

- Overall MAE rises from **45.0380** on validation to **57.8926** on test; RMSE rises from **178.7213** to **302.3691**.
- R2 declines from **0.774593** to **0.467902**, evidence of temporal generalization loss.
- Test MAE by magnitude is small **28.0416**, medium **46.3275**, large **153.3435**, and peak **1127.2386**.
- Peak test RMSE is **2708.6126** and peak R2 is **-0.495972**; extreme consumption remains the main residual-risk concentration.
- Small-band R2 is strongly negative despite low absolute MAE because the band has little target variance and occasional large misses dominate squared error. Band MAE/RMSLE are more interpretable there.
- Validation-to-test peak MAE increases from **542.1242** to **1127.2386**, so this candidate should not be promoted without drift and extreme-event work.
