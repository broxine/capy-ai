# Workflow

## Default operating loop

1. RnD ingests prior reports, audits, docs, and target metadata.
2. Knowledge team updates the wiki with new entities, patterns, and contradictions.
3. Plan & Strategy turns patterns into testable hypotheses.
4. CEO Orchestrator delegates focused tasks to Execution workers.
5. Execution captures evidence through passive recon or non-destructive validation.
6. Knowledge team stores durable learnings.
7. Evolution team crystallizes successful tactics into updated skills.

## Approval boundary

Semi-auto means:
- auto: research, planning, passive recon, safe validation prep, local simulation
- human approval required: live exploit execution against real assets

## Execution cadence

### Program intake
- load scope
- load bounty rules
- load known exclusions
- create program page in `knowledge/wiki/programs/`
- persist machine-readable profile in `knowledge/programs/`

### Hunt creation
- enumerate attack surfaces
- map trust boundaries
- pull analogous historical reports
- generate ranked hypotheses
- store campaign plan in `audit/plans/` and `knowledge/wiki/playbooks/`

### Safe validation
- reproduce with passive probes first
- move to non-destructive proof only if allowed by program policy
- collect logs, requests, responses, screenshots, and replay notes

### Learning loop
- append source artifact to `knowledge/raw/`
- update relevant wiki pages
- add or patch a skill if the workflow is reusable
- store false positives so the system stops wasting time on them

## Caveman handoff format

Use for internal summaries only:

```text
fact: reflected input validation absent on search parameter
impact: xss hypothesis worth manual browser validation
next: validator replay with benign payload in staging-safe path
```

## First operational target

Public bug bounty programs such as HackerOne, Immunefi, and Immutable-style surfaces. Phase 0 stops before autonomous live exploitation.

## Phase 1 concrete commands

```bash
python -m bughunter_hive.cli program-init --name "Target Name" --platform web2 --scope-domain app.target.tld
python -m bughunter_hive.cli report-mine --source /path/to/report.md --title "Prior writeup"
python -m bughunter_hive.cli campaign-plan --program target-name
python -m bughunter_hive.cli recon --target https://app.target.tld --program target-name --scope-domain target.tld
```

## Phase 2 orchestrated command

```bash
python -m bughunter_hive.cli orchestrate --manifest examples/phase2-manifest.json
python -m bughunter_hive.cli validate-plan --run audit/runs/example-hybrid-program-phase2-run.json
python -m bughunter_hive.cli validate-run --bundle audit/validation/example-hybrid-program-phase2-validation.json
python -m bughunter_hive.cli browser-validate --run audit/validation-runs/example-hybrid-program-phase3-validation-run.json
python -m bughunter_hive.cli browser-review --run audit/browser-validation-runs/example-hybrid-program-phase4-browser-validation.json
python -m bughunter_hive.cli triage --review audit/review-candidates/example-hybrid-program-phase5-review.json
python -m bughunter_hive.cli draft-disclosures --triage audit/triage/example-hybrid-program-phase6-triage.json
python -m bughunter_hive.cli feedback-template --triage audit/triage/example-hybrid-program-phase6-triage.json
python -m bughunter_hive.cli learn --triage audit/triage/example-hybrid-program-phase6-triage.json --feedback audit/feedback-templates/example-hybrid-program-phase7-feedback-template.json
```

The manifest-driven run is still constrained to safe operations. It composes the same internal modules used in Phase 1, then writes a run bundle into `audit/runs/` and a markdown handoff page into `knowledge/wiki/playbooks/`.

The validation bundle turns the Phase 2 run into the next Execution queue without crossing into live exploit behavior.

The validator runner is the first execution loop that consumes that queue. It remains read-only and artifact-first: request traces, notes, and summaries before any human considers stronger validation.

The browser validator is the visual lane on top of that: it captures screenshot and DOM evidence, still read-only, so reviewers can inspect actual rendered surfaces before approving anything stronger.

The browser reviewer then converts those visual/DOM artifacts into sharper candidate findings and next-safe-step guidance for triage.

The triage and disclosure stages then compress the candidate cloud into ranked findings and draft reports, so the system starts resembling an actual bug bounty production line instead of a pile of clues.

The learning loop closes that production line. Once a human marks findings as confirmed, weak, or false-positive, the system can stop hallucinating the same mistakes forever — at least in theory, which is already better than most bots.
