# Knowledge schema

This repository uses a persistent wiki pattern.

## Layers

### Raw sources
`knowledge/raw/`

Immutable artifacts:
- bug reports
- audit competition writeups
- docs snapshots
- target notes

Agents may add new files here but must not rewrite historical source content.

### Wiki
`knowledge/wiki/`

Synthesized pages maintained by agents:
- `index.md`
- `patterns/`
- `programs/`
- `findings/`
- `playbooks/`

The wiki is allowed to evolve. Pages should cross-link instead of duplicating knowledge.

### Schema + ledger
- `knowledge/SCHEMA.md` is the maintenance contract.
- `knowledge/catalog/sources.jsonl` is the source ledger.
- `knowledge/programs/*.json` is the machine-readable target profile store.

## Ingest rules

1. Save the raw source first.
2. Update or create the relevant wiki page.
3. Record contradictions explicitly.
4. Extract reusable methodology into `playbooks/` or `skills/` when warranted.
5. Record false positives and invalid assumptions.
6. For target programs, keep a JSON profile in `knowledge/programs/` and a readable mirror page in `knowledge/wiki/programs/`.

## Naming

- Use kebab-case file names.
- Prefer one entity or pattern per page.
- Findings pages must distinguish signal, validation, and impact.
