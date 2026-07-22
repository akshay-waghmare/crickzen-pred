# Plan

1. Add first-class CLI targets for `t20_all` and `odi_all`.
2. Run dataset audit for gender, match type, seasons, teams, and incomplete matches.
3. Run ingestion and processing into versioned `data/` directories.
4. Train v1 models and generate OOF calibration artifacts.
5. Compare overall and gender-sliced metrics against resource and existing-format baselines.
6. Register artifacts and verify live predictor construction.
