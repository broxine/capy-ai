# Bug Hunter Hive

Hermes-powered multi-agent scaffold for public bug bounty hunting across Web2 and Web3.

Phase 0 shipped the foundation:
- CEO-style orchestrator plus RnD, Plan & Strategy, Execution, Knowledge, and Evolution agents
- repo-local SOUL/AGENT/TOOLS definitions for each agent
- skill library for delegation, recon, validation, wiki ingest, and skill crystallization
- knowledge base structure inspired by the LLM Wiki pattern
- caveman-style compressed handoff convention for inter-agent summaries
- scope guard, audit log, and kill switch primitives
- one runnable recon sub-agent with tests

Phase 1 adds an actual hunt-prep pipeline:
- program profiling into JSON + wiki pages
- public report mining into persistent findings pages
- ranked campaign planning using a Web2/Web3 bug-class taxonomy
- audit plan artifacts for orchestrator handoff

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m bughunter_hive.cli killswitch status
python -m bughunter_hive.cli program-init \
  --name "Immutable Demo" \
  --platform web3 \
  --scope-domain api.example.com \
  --asset wallet-ui \
  --asset permit-api \
  --tag bridge \
  --note "check typed-data signing paths"
python -m bughunter_hive.cli campaign-plan --program immutable-demo
python -m bughunter_hive.cli recon \
  --target https://example.com \
  --program demo \
  --scope-domain example.com
pytest
```

## Hermes bootstrap

1. Run `hermes setup` and choose provider/model as you prefer.
2. Copy the delegation skeleton from `ops/hermes/config.yaml` into `~/.hermes/config.yaml`.
3. Install repo skills with `python -m bughunter_hive.cli bootstrap`.
4. Open this repo in Hermes. Root `AGENTS.md` and the `agents/` tree become the operating doctrine.

## Safety defaults

- Semi-auto until live exploitation.
- Passive recon is allowed when the target is in declared scope.
- Live exploit actions must carry explicit approval and are blocked by code in this phase.
- Every run writes JSONL audit events.
- A file-based kill switch can halt all automation immediately.

## Key docs

- `ARCHITECTURE.md`
- `workflow.md`
- `SOUL.md`
- `knowledge/SCHEMA.md`
- `ops/hermes/README.md`

## Phase 1 CLI surface

- `program-init` — create program JSON + wiki profile
- `report-mine` — ingest a public report into the persistent KB
- `campaign-plan` — rank first-pass hypotheses for a target program
- `recon` — run passive HTTP recon for one target
