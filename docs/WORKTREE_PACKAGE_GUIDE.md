# ⚠️ Worktree & Package Installation Guide

## The Problem

This repository uses **multiple git worktrees** that share the same codebase. When the `bbl-pipeline` package is installed in **editable mode** (`pip install -e .`), Python resolves imports from **whichever worktree was last installed** — not necessarily the one you're running from.

This causes **silent bugs** where the code in your terminal's working directory differs from the code Python actually executes.

## How Editable Installs Work

```bash
pip install -e .
```

This creates a `.egg-link` file in your Python `site-packages` that points to the **absolute path** of the worktree. All `import bbl_pipeline` statements resolve to that path.

### Current Worktrees

| Worktree | Path | Branch |
|----------|------|--------|
| Primary | `C:\Users\ADMINS\Documents\projects\machine_learning_bbl` | `001-mc-ml-direction-model` |
| ODI/MC | `C:\Users\ADMINS\Documents\projects\machine_learning_bbl_009-odi-mc-predictor` | `009-odi-mc-predictor` |
| Death Overs | `C:\Users\ADMINS\Documents\projects\machine_learning` | `004-death-overs-mc` |

## How to Check Which Worktree Is Active

```bash
python -c "import bbl_pipeline; print(bbl_pipeline.__file__)"
```

Or for a specific module:

```bash
python -c "import bbl_pipeline.features.format_config as m; print(m.__file__)"
```

**Expected output** should match your current working directory's worktree. If it doesn't, you need to reinstall.

## How to Switch the Active Worktree

```bash
# Navigate to the worktree you want to use
cd C:\Users\ADMINS\Documents\projects\machine_learning_bbl_009-odi-mc-predictor

# Reinstall in editable mode
pip install -e .
```

## Real-World Example: The IPL par_score Bug

During an IPL live prediction session, the `par_score` showed **173.45** (from the IPL-specific `FormatConfig.ipl()` in the primary worktree) even though the source code in the current worktree only had the generic T20 config with `par_score=160.0`.

**Root cause:** The package was installed from `machine_learning_bbl` (which had `FormatConfig.ipl()`) but the user was working in `machine_learning_bbl_009-odi-mc-predictor` (which didn't have it yet).

**How to diagnose:**
```bash
# 1. Check what value Python sees
python -c "from bbl_pipeline.features.format_config import FormatConfig; print(FormatConfig.from_league('ipl').par_score)"

# 2. Check where the module is loaded from
python -c "import bbl_pipeline.features.format_config as m; print(m.__file__)"

# 3. If the path doesn't match your worktree, reinstall
pip install -e .
```

## Best Practices

1. **Always verify** the active worktree after switching between directories
2. **Reinstall** (`pip install -e .`) whenever you switch to a different worktree for development
3. **Before live prediction sessions**, confirm the package source matches your working directory
4. **After making code changes**, no reinstall needed if already installed from the same worktree (editable mode picks up file changes automatically)
5. **Use the launcher app** (`python scripts/launcher.py`) which displays the active package source on startup
