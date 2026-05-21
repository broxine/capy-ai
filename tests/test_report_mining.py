from pathlib import Path

from bughunter_hive.report_mining import mine_report


def test_mine_report_creates_finding_page(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text(
        (
            "# Demo report\n"
            "This writeup shows an OAuth session mix-up that leads to account takeover.\n"
            "Proof of concept and steps to reproduce are included.\n"
        ),
        encoding="utf-8",
    )

    summary = mine_report(
        repo_root=tmp_path,
        source_path=report,
        title="OAuth Session Mixup",
        kind="report",
        reference_url="https://example.com/report",
    )

    assert "auth-session" in summary.bug_classes
    assert "proof of concept" in summary.validation_clues
    finding_page = tmp_path / "knowledge" / "wiki" / "findings" / "oauth-session-mixup.md"
    assert "account takeover" in finding_page.read_text(encoding="utf-8")
