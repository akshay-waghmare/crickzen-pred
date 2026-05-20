# Codex Skills

This repository has a reusable Codex skill for starting the dashboard:

- Skill name: `start-dashboard`
- Purpose: start or restart the dashboard app and verify `http://127.0.0.1:8000/health`
- Skill location: `C:\Users\ADMINS\.codex\skills\start-dashboard`
- Usage: invoke it with `$start-dashboard`

The skill uses the repo's dashboard launcher and a persistent Windows launch path so the app stays up after the shell session ends.

It also has a reusable IPL model research skill:

- Skill name: `ipl-market-model-comparison`
- Purpose: inspect latest IPL Cricsheet/betx21 coverage, refresh non-active latest features, and rerun the IPL MC market-improvement workflow.
- Skill location: `C:\Users\ADMINS\.codex\skills\ipl-market-model-comparison`
- Usage: invoke it with `$ipl-market-model-comparison`
