# Safe Validation

Validate without damage:
- use passive or clearly reversible probes first
- capture replay steps
- stop when proof is sufficient
- record false positives aggressively

Phase 2 helper:
```bash
python -m bughunter_hive.cli validate-plan --run audit/runs/<program>-phase2-run.json
```
