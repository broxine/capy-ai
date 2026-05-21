# Repo operating doctrine

- Hermes is the orchestrator runtime for this repo.
- Read `ARCHITECTURE.md`, `workflow.md`, `SOUL.md`, and `knowledge/SCHEMA.md` before changing agent doctrine.
- Use the `agents/` directory as the source of truth for role boundaries.
- Use the `skills/` directory as the reusable execution library.
- Internal agent handoffs should default to caveman format: `fact -> impact -> next`.
- Do not perform live exploitation against real targets without explicit human approval.
- All execution must respect `scope-guard`, `audit-log`, and `kill-switch`.
- Prefer adding knowledge pages and skill patches over burying learnings in chat history.
