from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bughunter_hive.browser_review import review_browser_validation
from bughunter_hive.browser_validator import run_browser_validation
from bughunter_hive.disclosure import generate_disclosure_drafts
from bughunter_hive.learning import create_feedback_template, run_learning_loop
from bughunter_hive.orchestrator import run_orchestrator_from_manifest
from bughunter_hive.triage import triage_review_candidates
from bughunter_hive.validation import build_validation_bundle
from bughunter_hive.validator_runner import execute_validation_bundle


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><title>Learning Target</title><body><form action='/login'><input name='email'></form><script>window.postMessage('x','*');</script>oauth callback wallet permit</body></html>"
            )
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def test_learning_loop_generates_recommendations(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        report = tmp_path / "report.md"
        report.write_text("OAuth confusion with proof of concept and account takeover.", encoding="utf-8")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "program": {
                        "name": "Learning Demo",
                        "platform": "hybrid",
                        "program_url": "https://example.com/program",
                        "scope_domains": ["127.0.0.1"],
                        "assets": ["public-api", "oauth-callback", "wallet-ui"],
                        "exclusions": ["live exploit"],
                        "tags": ["oauth", "api", "wallet"],
                        "notes": ["check callback binding"],
                    },
                    "reports": [{"source": str(report), "title": "Learning Report", "kind": "report"}],
                    "recon_targets": [f"http://127.0.0.1:{server.server_port}"],
                    "allow_private_targets": True,
                    "plan_limit": 2,
                }
            ),
            encoding="utf-8",
        )
        run_path = run_orchestrator_from_manifest(
            repo_root=tmp_path,
            manifest_path=manifest,
            audit_log_path=tmp_path / "events.jsonl",
            kill_switch_path=tmp_path / "kill.flag",
        )
        bundle_path = build_validation_bundle(tmp_path, run_path, max_tasks=2)
        validation_run_path = execute_validation_bundle(
            repo_root=tmp_path,
            bundle_path=bundle_path,
            audit_log_path=tmp_path / "events.jsonl",
            kill_switch_path=tmp_path / "kill.flag",
            allow_private_targets=True,
        )
        browser_run_path = run_browser_validation(
            repo_root=tmp_path,
            validation_run_path=validation_run_path,
            audit_log_path=tmp_path / "events.jsonl",
            kill_switch_path=tmp_path / "kill.flag",
        )
        review_path = review_browser_validation(
            repo_root=tmp_path,
            browser_validation_path=browser_run_path,
            audit_log_path=tmp_path / "events.jsonl",
        )
        triage_path = triage_review_candidates(
            repo_root=tmp_path,
            review_path=review_path,
            audit_log_path=tmp_path / "events.jsonl",
        )
        _ = generate_disclosure_drafts(
            repo_root=tmp_path,
            triage_path=triage_path,
            audit_log_path=tmp_path / "events.jsonl",
            max_drafts=2,
        )
        template_path = create_feedback_template(repo_root=tmp_path, triage_path=triage_path)
        template = json.loads(template_path.read_text(encoding="utf-8"))
        assert template["outcomes"]
        template["outcomes"][0]["verdict"] = "confirmed"
        template["outcomes"][0]["notes"] = "matched real auth callback issue"
        if len(template["outcomes"]) > 1:
            template["outcomes"][1]["verdict"] = "false_positive"
            template["outcomes"][1]["notes"] = "wallet copy present but no signing flow"
        feedback_path = tmp_path / "feedback.json"
        feedback_path.write_text(json.dumps(template), encoding="utf-8")
        learning_path = run_learning_loop(
            repo_root=tmp_path,
            triage_path=triage_path,
            feedback_path=feedback_path,
            audit_log_path=tmp_path / "events.jsonl",
        )
        payload = json.loads(learning_path.read_text(encoding="utf-8"))
        assert payload["program_slug"] == "learning-demo"
        assert payload["outcomes_recorded"]
        assert payload["cluster_stats"]
    finally:
        server.shutdown()
        server.server_close()
