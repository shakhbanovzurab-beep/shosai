---
name: python-doctor
description: Use when finishing a feature, fixing a bug, or before committing Python code, and when the user asks to scan, check health, or clean up Python diagnostics. Runs the python-doctor CLI (security, lint, complexity, zen, structure, exceptions, imports) and returns a 0-100 health score. Project target is 100/100.
---

# Python Doctor

Scans a Python codebase and returns a 0–100 health score with actionable findings.
Wraps `ruff`, `bandit`, `radon` and `vulture` plus structure, exception and import checks.

Upstream: https://github.com/saikatkumardey/python-doctor (the repository ships no
skill file; this one follows the agent loop from its README).

## Project target

**100/100.** Work on Python code is not finished while the score is below 100.

## After making Python code changes

Run from the directory that holds the Python project (here: `backend/`):

```bash
python-doctor . --json
```

Then loop:

1. Read the report: `score`, and the findings per category.
2. Fix findings — `python-doctor . --fix` for what ruff can auto-fix, by hand for the rest.
   Errors first, then warnings.
3. `python-doctor . --score` to verify.
4. Repeat until the score is 100.

Fix the code, not the score: do not silence a finding with `# noqa`, `# nosec` or a
config exclusion unless it is a verified false positive, and say so when you do.

If 100 cannot be reached, report the remaining findings and why, rather than
claiming the target was met.

## Command

| Flag | Purpose |
| --- | --- |
| `.` | Directory to scan |
| `--verbose` | Show all findings with file and line |
| `--json` | Structured output for parsing |
| `--score` | Print only the numeric score |
| `--fix` | Auto-fix what ruff can fix |
| `--profile {cli,web,library,script}` | Override the auto-detected project profile |
| `--min-score N` | Exit 1 if the score is below N (default 50) |
| `--strict` | Exit 2 if the score regressed against the cached state |
| `--no-cache` | Do not read or write `.python-doctor/state.json` |

Each run writes `.python-doctor/state.json` and the next run shows the delta.

## Install or update

```bash
pipx install python-doctor      # first install
pipx upgrade python-doctor      # update to the latest release
```
