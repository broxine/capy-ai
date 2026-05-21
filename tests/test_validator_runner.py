from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bughunter_hive.orchestrator import run_orchestrator_from_manifest
from bughunter_hive.validation import build_validation_bundle
from bughunter_hive.validator_runner import execute_validation_bundle


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><title>Runner Target</title><body><a href='/users/42'>User</a><form><input name='q'></form>oauth callback</body></html>"
            )
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def test_execute_validation_bundle_writes_artifacts(tmp_path: Path) -> None:
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
                        "name": "Runner Demo",
                        "platform": "hybrid",
                        "program_url": "https://example.com/program",
                        "scope_domains": ["127.0.0.1"],
                        "assets": ["public-api", "oauth-callback"],
                        "exclusions": ["live exploit"],
                        "tags": ["oauth", "api"],
                        "notes": ["check callback binding"],
                    },
                    "reports": [{"source": str(report), "title": "Runner Report", "kind": "report"}],
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
        result_path = execute_validation_bundle(
            repo_root=tmp_path,
            bundle_path=bundle_path,
            audit_log_path=tmp_path / "events.jsonl",
            kill_switch_path=tmp_path / "kill.flag",
            allow_private_targets=True,
        )

        payload = json.loads(result_path.read_text(encoding="utf-8"))
        assert payload["program_slug"] == "runner-demo"
        assert payload["executions"]
        assert payload["executions"][0]["request_artifact"].endswith(".http")
        assert payload["executions"][0]["note_artifact"].endswith(".md")
        notes_path = tmp_path / payload["executions"][0]["note_artifact"]
        assert "Observations" in notes_path.read_text(encoding="utf-8")
    finally:
        server.shutdown()
        server.server_close()
