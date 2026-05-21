# Delegate and Scope

Use when the orchestrator needs to split work.

Rules:
1. Pass exact target, scope, exclusions, and desired output.
2. Delegate to no more than three concurrent children.
3. Children return caveman summary plus artifact paths.
4. Any live exploit path bounces back for approval.

Phase 2 helper:
```bash
python -m bughunter_hive.cli orchestrate --manifest examples/phase2-manifest.json
```
