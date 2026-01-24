# Women's Super Smash (WSSM)

**League Code**: `wssm` (to distinguish from male SSM)

**Data Source**: Cricsheet - Women's Super Smash matches
**Matches**: 186 JSON files
**Format**: T20

## Usage

### Extract Phase Distributions
```bash
python scripts/analysis/extract_phase_distributions.py \
  --json-dir wssm_female_json \
  --league wssm
```

**Output**: `data/phase_distributions_wssm.json`

### Use in Predictions
```python
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.simulation.sampler import NextBallSampler

# Load unified female model with WSSM league
predictor = Predictor.load("models/t20_female_v3", league="wssm")

# Sampler automatically loads wssm distributions
sampler = NextBallSampler(league="wssm")
# → Loads from: data/phase_distributions_wssm.json
```

## Naming Convention

To avoid confusion between male and female leagues:

| League | Gender | Code | Model | Distribution File |
|--------|--------|------|-------|-------------------|
| Super Smash | Male | `ssm` | `models/ssm_v1` | `phase_distributions_ssm.json` |
| Super Smash | Female | `wssm` | `models/t20_female_v3` | `phase_distributions_wssm.json` |

**WSSM** = **W**omen's **S**uper **S**mash
