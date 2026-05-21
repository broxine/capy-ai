from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bughunter_hive.orchestrator import run_orchestrator_from_manifest


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Server", "phase2-test")
            self.end_headers()
            self.wfile.write(b"<html><title>Phase2 Target</title><body>Hello</body></html>")
            return
        if self.path == "/robots.txt":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"User-agent: *\nDisallow: /admin\n")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def test_run_orchestrator_from_manifest_builds_bundle(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        report = tmp_path / "report.md"
        report.write_text(
            "OAuth session confusion with proof of concept and account takeover.",
            encoding="utf-8",
        )
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "program": {
                        "name": "Phase2 Demo",
                        "platform": "hybrid",
                        "program_url": "https://example.com/program",
                        "scope_domains": ["127.0.0.1"],
                        "assets": ["public-api", "oauth-callback"],
                        "exclusions": ["live exploit"],
                        "tags": ["oauth", "api"],
                        "notes": ["check callback binding"],
                    },
                    "reports": [
                        {
                            "source": str(report),
                            "title": "OAuth Session Confusion",
                            "kind": "report",
                        }
                    ],
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

        payload = json.loads(run_path.read_text(encoding="utf-8"))
        assert payload["program_slug"] == "phase2-demo"
        assert payload["report_titles"] == ["OAuth Session Confusion"]
        assert payload["top_hypotheses"]
        assert payload["recon_reports"]
        assert "ceo" in payload["team_handoffs"]
        playbook = tmp_path / "knowledge" / "wiki" / "playbooks" / "phase2-demo-phase2-run.md"
        assert "Phase 2 orchestrator run" in playbook.read_text(encoding="utf-8")
    finally:
        server.shutdown()
        server.server_close()
