# Surgical Task Checklist

- [ ] Audit every `projected_score` dependency and classify it as display-only, training feature, inference feature, or derived feature.
- [ ] Add the expected-final venue-relative feature to historical processing and live inference with identical formulas.
- [ ] Define candidate-only feature ordering that excludes all projected-score-derived fields.
- [ ] Add tests proving candidate feature inputs contain no projected-score fields and that expected-final venue-relative values match.
- [ ] Add isolated T20 candidate training target and metadata.
- [ ] Add isolated ODI candidate training target and metadata.
- [ ] Train both candidates without modifying v2 artifacts or production routing.
- [ ] Run chronological train-before-2025/test-2025+ evaluation for overall, male, and female slices.
- [ ] Compare Brier score, log loss, calibration/ECE, and sample counts against v2.
- [ ] Run model-load and dashboard prediction-path smoke tests.
- [ ] Promote only if all/male/female gates pass; otherwise retain v2.
- [ ] Record the final decision in repo documentation and the Obsidian wiki.
