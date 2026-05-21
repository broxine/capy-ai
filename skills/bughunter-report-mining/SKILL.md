# Report Mining

1. Collect public disclosures, audits, contests, and docs.
2. Extract: target type, bug class, primitive, validator signal, and why it was missed.
3. Save raw artifact first.
4. Update the wiki pattern page second.

Repo helper:
```bash
python -m bughunter_hive.cli report-mine --source /path/to/report.md --title "Writeup title"
```
