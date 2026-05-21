from pathlib import Path

from bughunter_hive.knowledge import register_source


def test_register_source_creates_catalog_entry(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "knowledge" / "catalog").mkdir(parents=True)
    source = tmp_path / "report.md"
    source.write_text("hello", encoding="utf-8")
    record = register_source(repo, source, title="Test Report", kind="report")
    assert record.kind == "report"
    catalog = (repo / "knowledge" / "catalog" / "sources.jsonl").read_text(encoding="utf-8")
    assert "Test Report" in catalog
