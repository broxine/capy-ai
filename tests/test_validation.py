from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bughunter_hive.orchestrator import run_orchestrator_from_manifest
from bughunter_hive.validation import build_validation_bundle


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><title>Validation Target</title><body>Hello</body></html>")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def test_build_validation_bundle_from_run(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        report = tmp_path / "report.md"
        report.write_text(
            "OAuth confusion with proof of concept and account takeover.",
            encoding="utf-8",
        )
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "program": {
                        "name": "Validation Demo",
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
                            "title": "OAuth Validation Report",
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

        bundle_path = build_validation_bundle(tmp_path, run_path, max_tasks=2)
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        assert bundle["program_slug"] == "validation-demo"
        assert bundle["tasks"]
        assert bundle["tasks"][0]["bug_class_id"] == "web2-auth-session"
        assert "reversible checks" in bundle["tasks"][0]["caveman_handoff"]
        md_path = tmp_path / "knowledge" / "wiki" / "playbooks" / "validation-demo-phase2-validation.md"
        assert "Phase 2 validation bundle" in md_path.read_text(encoding="utf-8")
    finally:
        server.shutdown()
        server.server_close()
