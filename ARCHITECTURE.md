# Architecture

## Objective

Build a multi-agent security research system that can discover, validate, and learn from real bug bounty findings without drifting into unsafe automation.

Acceptance target for Phase 0: a repository scaffold that can host Hermes-based orchestration, persist institutional knowledge, enforce safety gates, and run one real recon worker end to end.

Acceptance target for Phase 1: convert the scaffold into a usable pre-execution pipeline that can profile a public program, mine prior reports into persistent findings, rank hypotheses, and hand off a safe campaign plan to execution workers.

## Org chart

```text
CEO Orchestrator
├── RnD Team
│   ├── Report Miner
│   └── Attack Surface Analyst
├── Plan & Strategy Team
│   ├── Hypothesis Architect
│   └── Campaign Quartermaster
├── Execution Team
│   ├── Recon Scout
│   └── Validator
├── Knowledge Team
│   └── Wiki Curator
└── Evolution Team
    └── Skillsmith
```

## Runtime model

- Hermes is the orchestrator runtime.
- The repo provides doctrine, prompts, skills, safety policy, and local helper tools.
- Orchestrator gets delegation authority but no permission to bypass scope guard.
- Execution workers operate on narrow tasks with explicit context, tool bounds, and approval rules.

## Team contracts

### CEO Orchestrator
- Owns decomposition, prioritization, delegation, and stop/go decisions.
- Uses caveman handoffs for terse child summaries.
- Never performs live exploitation without explicit approval state from the human.

### RnD
- Mines public reports, audit contests, docs, changelogs, prior disclosures, and protocol design material.
- Converts raw artifacts into reusable patterns and attack hypotheses.
- Phase 1 implementation surface: `report-mine`.

### Plan & Strategy
- Converts RnD output into scoped campaigns, test hypotheses, and validation plans.
- Chooses what to test first based on likelihood, blast radius, novelty, and reversibility.
- Phase 1 implementation surface: `program-init` + `campaign-plan`.

### Execution
- Performs passive recon, non-destructive validation, artifact capture, and reproducible evidence generation.
- Recon Scout is the first runnable worker in this phase.

### Knowledge
- Maintains a persistent wiki instead of one-shot RAG.
- Stores immutable raw sources separately from synthesized pages.

### Evolution
- Turns postmortems and successful hunts into new or improved skills.
- Tracks which workflow variants worked, where they failed, and what should become doctrine.

## Safety spine

Three hard controls exist from day one:

1. `scope-guard` — target scheme, host, and declared scope are checked before execution.
2. `audit-log` — every run emits structured JSON events for replay and review.
3. `kill-switch` — file-based stop flag blocks new work immediately.

Live exploitation is intentionally not implemented in Phase 0. The policy layer already reserves the approval gate for it.

## Knowledge architecture

Inspired by Karpathy's LLM Wiki pattern:

- `knowledge/raw/` contains immutable source artifacts.
- `knowledge/wiki/` contains synthesized markdown pages owned by agents.
- `knowledge/SCHEMA.md` defines the maintenance contract.
- `knowledge/catalog/sources.jsonl` is the machine-readable source ledger.

This avoids rediscovering the same bug classes from scratch every session.

## Caveman usage

Caveman is applied to internal handoffs, not final evidence. The rule is:

- user-facing proofs stay explicit and complete
- inter-agent summaries stay compressed: `fact -> impact -> next`

This reduces token burn during multi-agent fan-out while keeping final reports readable.

## Repository map

- `agents/` — role definitions
- `skills/` — reusable playbooks
- `src/bughunter_hive/` — local helper runtime and safety primitives
- `ops/hermes/` — Hermes bootstrap assets
- `knowledge/` — persistent wiki structure
- `policy/` — approval and scope doctrine
- `tests/` — verification

## Phase 0 shipped component

`bughunter_hive.recon` performs safe HTTP recon:
- base page fetch
- header inspection
- `robots.txt` discovery
- `security.txt` discovery
- HTML title extraction
- structured findings and audit artifacts

It is intentionally passive and produces signals, not destructive actions.

## Phase 1 shipped components

- `bughunter_hive.programs` writes durable program profiles to `knowledge/programs/` and mirrored wiki pages.
- `bughunter_hive.report_mining` ingests public writeups into `knowledge/raw/` plus synthesized findings pages.
- `bughunter_hive.planning` ranks first-pass hypotheses from a curated taxonomy spanning Web2 and Web3 bug classes.
- `audit/plans/` stores machine-readable plan artifacts for the orchestrator.
