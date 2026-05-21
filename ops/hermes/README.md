# Hermes bootstrap notes

This repo does not try to replace `hermes setup`. Use Hermes' own setup flow for provider/model/API credentials.

Then:
1. Merge the delegation block from `ops/hermes/config.yaml` into `~/.hermes/config.yaml`.
2. Run `python -m bughunter_hive.cli bootstrap` to copy repo skills into `~/.hermes/skills/`.
3. Start Hermes inside this repo so it can read `AGENTS.md`, `SOUL.md`, and the `agents/` directory.
4. Use `program-init`, `report-mine`, and `campaign-plan` to seed the knowledge base before delegating recon.

Suggested first prompt inside Hermes:

```text
You are the CEO Orchestrator in this repo. Read AGENTS.md, ARCHITECTURE.md, workflow.md, and agents/orchestrator/ceo/. Build a first-pass delegation plan for passive recon of a public bug bounty target without performing live exploitation.
```
