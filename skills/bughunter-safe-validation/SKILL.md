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

Phase 3 helper:
```bash
python -m bughunter_hive.cli validate-run --bundle audit/validation/<program>-phase2-validation.json
```

Phase 4 helper:
```bash
python -m bughunter_hive.cli browser-validate --run audit/validation-runs/<program>-phase3-validation-run.json
```
