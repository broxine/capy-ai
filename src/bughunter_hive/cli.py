from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bootstrap import install_repo_skills
from .killswitch import KillSwitch, KillSwitchEngaged
from .knowledge import register_source
from .orchestrator import run_orchestrator_from_manifest
from .planning import build_campaign_plan
from .programs import load_program_profile, write_program_profile
from .recon import run_recon
from .report_mining import mine_report
from .validation import build_validation_bundle


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _print(data: object) -> None:
    print(json.dumps(data, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bughunter")
    sub = parser.add_subparsers(dest="command", required=True)

    recon = sub.add_parser("recon", help="run passive recon")
    recon.add_argument("--target", required=True)
    recon.add_argument("--program", required=True)
    recon.add_argument("--scope-domain", action="append", default=[])
    recon.add_argument("--allow-private", action="store_true")
    recon.add_argument("--timeout", type=int, default=10)
    recon.add_argument("--audit-log", default=str(_repo_root() / "audit" / "events.jsonl"))
    recon.add_argument("--artifacts-dir", default=str(_repo_root() / "audit" / "recon"))
    recon.add_argument("--kill-switch", default=str(_repo_root() / "runtime" / "kill-switch.flag"))

    ks = sub.add_parser("killswitch", help="manage kill switch")
    ks_sub = ks.add_subparsers(dest="killswitch_command", required=True)
    for name in ("status", "clear"):
        cmd = ks_sub.add_parser(name)
        cmd.add_argument("--path", default=str(_repo_root() / "runtime" / "kill-switch.flag"))
    engage = ks_sub.add_parser("engage")
    engage.add_argument("reason")
    engage.add_argument("--path", default=str(_repo_root() / "runtime" / "kill-switch.flag"))

    kb = sub.add_parser("kb-add-source", help="register a knowledge source")
    kb.add_argument("--source", required=True)
    kb.add_argument("--title", required=True)
    kb.add_argument("--kind", default="report")
    kb.add_argument("--slug")

    program = sub.add_parser("program-init", help="create a program profile and wiki page")
    program.add_argument("--name", required=True)
    program.add_argument("--platform", choices=["web2", "web3", "hybrid"], required=True)
    program.add_argument("--program-url")
    program.add_argument("--scope-domain", action="append", default=[])
    program.add_argument("--asset", action="append", default=[])
    program.add_argument("--exclusion", action="append", default=[])
    program.add_argument("--tag", action="append", default=[])
    program.add_argument("--note", action="append", default=[])

    report = sub.add_parser("report-mine", help="ingest a public report into the knowledge base")
    report.add_argument("--source", required=True)
    report.add_argument("--title", required=True)
    report.add_argument("--kind", default="report")
    report.add_argument("--reference-url")

    plan = sub.add_parser("campaign-plan", help="build a ranked Phase 1 hypothesis plan")
    plan.add_argument("--program", required=True, help="program slug or json path")
    plan.add_argument("--limit", type=int, default=5)

    orchestrate = sub.add_parser("orchestrate", help="run the Phase 2 end-to-end safe workflow from a manifest")
    orchestrate.add_argument("--manifest", required=True)
    orchestrate.add_argument("--audit-log", default=str(_repo_root() / "audit" / "events.jsonl"))
    orchestrate.add_argument("--kill-switch", default=str(_repo_root() / "runtime" / "kill-switch.flag"))

    validate = sub.add_parser("validate-plan", help="build a safe validation bundle from an orchestrator run")
    validate.add_argument("--run", required=True)
    validate.add_argument("--max-tasks", type=int, default=3)

    bootstrap = sub.add_parser("bootstrap", help="copy repo skills into Hermes home")
    bootstrap.add_argument("--hermes-home", default=str(Path.home() / ".hermes"))
    bootstrap.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = _repo_root()

    try:
        if args.command == "recon":
            path = run_recon(
                target=args.target,
                program=args.program,
                scope_domains=args.scope_domain,
                audit_path=Path(args.audit_log),
                artifacts_dir=Path(args.artifacts_dir),
                kill_switch_path=Path(args.kill_switch),
                allow_private_targets=args.allow_private,
                timeout=args.timeout,
            )
            _print({"report_path": str(path)})
            return 0

        if args.command == "killswitch":
            switch = KillSwitch(Path(args.path))
            if args.killswitch_command == "status":
                _print(switch.status())
                return 0
            if args.killswitch_command == "engage":
                switch.engage(args.reason)
                _print(switch.status())
                return 0
            if args.killswitch_command == "clear":
                switch.clear()
                _print(switch.status())
                return 0

        if args.command == "kb-add-source":
            record = register_source(
                repo_root=repo_root,
                source_path=Path(args.source),
                title=args.title,
                kind=args.kind,
                slug=args.slug,
            )
            _print(record.__dict__)
            return 0

        if args.command == "program-init":
            profile = write_program_profile(
                repo_root=repo_root,
                name=args.name,
                platform=args.platform,
                program_url=args.program_url,
                scope_domains=args.scope_domain,
                assets=args.asset,
                exclusions=args.exclusion,
                tags=args.tag,
                notes=args.note,
            )
            _print(profile.__dict__)
            return 0

        if args.command == "report-mine":
            summary = mine_report(
                repo_root=repo_root,
                source_path=Path(args.source),
                title=args.title,
                kind=args.kind,
                reference_url=args.reference_url,
            )
            _print(
                {
                    "source": summary.source.__dict__,
                    "title": summary.title,
                    "finding_slug": summary.finding_slug,
                    "bug_classes": summary.bug_classes,
                    "validation_clues": summary.validation_clues,
                    "impact_clues": summary.impact_clues,
                }
            )
            return 0

        if args.command == "campaign-plan":
            profile = load_program_profile(repo_root, args.program)
            plan = build_campaign_plan(repo_root, profile, limit=args.limit)
            _print(
                {
                    "program_slug": plan.program_slug,
                    "generated_at": plan.generated_at,
                    "hypotheses": [item.__dict__ for item in plan.hypotheses],
                }
            )
            return 0

        if args.command == "orchestrate":
            run_path = run_orchestrator_from_manifest(
                repo_root=repo_root,
                manifest_path=Path(args.manifest),
                audit_log_path=Path(args.audit_log),
                kill_switch_path=Path(args.kill_switch),
            )
            _print({"run_path": str(run_path)})
            return 0

        if args.command == "validate-plan":
            bundle_path = build_validation_bundle(
                repo_root=repo_root,
                run_path=Path(args.run),
                max_tasks=args.max_tasks,
            )
            _print({"bundle_path": str(bundle_path)})
            return 0

        if args.command == "bootstrap":
            copied = install_repo_skills(repo_root=repo_root, hermes_home=Path(args.hermes_home), force=args.force)
            _print({"copied": [str(path) for path in copied]})
            return 0
    except (PermissionError, ValueError, FileNotFoundError, KillSwitchEngaged) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
