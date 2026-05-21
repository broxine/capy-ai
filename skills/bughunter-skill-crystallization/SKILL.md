# Skill Crystallization

Promote a workflow into a skill when:
- it worked at least twice, or
- it killed false positives consistently, or
- it compressed token use without losing evidence quality

Phase 7 learning helpers:
```bash
python -m bughunter_hive.cli feedback-template --triage audit/triage/<program>-phase6-triage.json
python -m bughunter_hive.cli learn --triage audit/triage/<program>-phase6-triage.json --feedback audit/feedback-templates/<program>-phase7-feedback-template.json
```
