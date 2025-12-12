---
description: Predict T20 match outcomes (Win Probability, Projected Score) from natural language commentary using the local machine learning model.
---

## User Input

```text
$ARGUMENTS
```

The user input will be a string of cricket commentary or a match state description (e.g., "India 120/2 after 12.4 overs vs SA").

## Goal

Parse the user's natural language commentary to extract the current match state, then execute the local `scripts/quick_predict.py` script to generate a win probability and projected score.

## Operating Constraints

- **ReadOnly**: Do not modify any files.
- **Script Usage**: MUST use `python scripts/quick_predict.py` for the calculation. Do not try to emulate the model's math in the prompt.
- **Output Format**: Present the result in a clear, formatted table.

## Execution Steps

### 1. Parse Match State

Analyze the `$ARGUMENTS` to extract the following entities. Infer missing values if reasonable defaults exist (e.g., if target is not mentioned, assume 1st innings).

- **Batting Team** (`--batting`)
- **Bowling Team** (`--bowling`)
- **Score** (`--score`)
- **Wickets** (`--wickets`)
- **Overs** (`--overs`)
- **Target** (`--target`) [Optional]

*Heuristics:*
- "120/2" -> Score: 120, Wickets: 2
- "12.4 overs" -> Overs: 12.4
- "chasing 180" -> Target: 180

### 2. Execute Prediction Model

Construct and run the terminal command using the extracted values.

```bash
python scripts/quick_predict.py --batting "{BattingTeam}" --bowling "{BowlingTeam}" --score {Score} --wickets {Wickets} --overs {Overs} [--target {Target}]
```

### 3. Report Results

Parse the output from the script (which returns `WIN_PROBABILITY`, `PROJECTED`, `RESOURCE_PROB`) and display it to the user in the following format:

### 🏏 Match Prediction

**{BattingTeam} vs {BowlingTeam}**
*State: {Score}/{Wickets} ({Overs} ov)*

| Metric | Value |
| :--- | :--- |
| **Win Probability ({BattingTeam})** | **{WinProb}%** |
| **Projected Score** | **{Projected}** |
| **DLS/Resource Win Prob** | {ResourceProb}% |

*(If chasing)*: Needs {RunsNeeded} runs in {BallsRemaining} balls.

## Context

$ARGUMENTS
