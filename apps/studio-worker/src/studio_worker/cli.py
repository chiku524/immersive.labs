from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from studio_worker import __version__
from studio_worker.attribution import write_pack_attribution
from studio_worker.job_runner import run_studio_job
from studio_worker.pack_writer import write_pack
from studio_worker.spec_generate import generate_asset_spec_with_metadata
from studio_worker.validate import validate_asset_spec_file


def _cmd_queue_worker(args: argparse.Namespace) -> int:
    from studio_worker.sqlite_queue import run_worker_loop

    run_worker_loop(
        worker_id=args.worker_id,
        poll_interval_s=args.poll_interval,
        run_once=args.once,
    )
    return 0


def _cmd_generate_spec(args: argparse.Namespace) -> int:
    try:
        spec, meta = generate_asset_spec_with_metadata(
            user_prompt=args.prompt,
            category=args.category,
            style_preset=args.style_preset,
            use_mock=args.mock,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2

    payload = {"spec": spec, "meta": meta}
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(spec, indent=2))
    return 0


def _cmd_validate_spec(args: argparse.Namespace) -> int:
    path = Path(args.file)
    try:
        validate_asset_spec_file(path)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


def _cmd_pack(args: argparse.Namespace) -> int:
    path = Path(args.spec)
    try:
        from studio_worker.validate import load_spec_document

        spec = load_spec_document(path)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1

    out = Path(args.output)
    try:
        manifest = write_pack(
            out,
            spec,
            job_id=None,
            llm_model=None,
            image_pipeline="comfyui:cli-pack",
            unity_urp_hint=args.unity_urp,
            write_spec_json=True,
        )
        write_pack_attribution(out, spec=spec, manifest=manifest, meta=None)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(json.dumps({"manifest_job_id": manifest["job_id"], "output_dir": str(out.resolve())}, indent=2))
    return 0


def _cmd_run_job(args: argparse.Namespace) -> int:
    try:
        result = run_studio_job(
            user_prompt=args.prompt,
            category=args.category,
            style_preset=args.style_preset,
            use_mock=args.mock,
            generate_textures=args.textures,
            unity_urp_hint=args.unity_urp,
            comfy_base_url=None,
            export_mesh=args.export_mesh,
        )
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "studio_worker.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _cmd_tenants(args: argparse.Namespace) -> int:
    from studio_worker import tenants_db

    tenants_db.init_tenants_schema()
    action = args.tenants_action
    if action == "create":
        tid = tenants_db.create_tenant(name=args.name, tier_id=args.tier)
        print(json.dumps({"tenant_id": tid, "tier": args.tier, "name": args.name}, indent=2))
        return 0
    if action == "list":
        print(json.dumps(tenants_db.list_tenants(), indent=2))
        return 0
    if action == "issue-key":
        raw = tenants_db.create_api_key(tenant_id=args.tenant_id, label=args.label)
        print(
            json.dumps(
                {
                    "api_key": raw,
                    "note": "Store this key securely; it cannot be retrieved again.",
                },
                indent=2,
            )
        )
        return 0
    if action == "set-tier":
        try:
            tenants_db.set_tenant_tier(args.tenant_id, args.tier)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        print(json.dumps({"tenant_id": args.tenant_id, "tier": args.tier}, indent=2))
        return 0
    print("Unknown tenants action", file=sys.stderr)
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="immersive-studio", description="Immersive Labs studio worker")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate-spec", help="Natural language → validated StudioAssetSpec JSON")
    g.add_argument("--prompt", required=True, help="Creative brief")
    g.add_argument(
        "--category",
        default="prop",
        choices=["prop", "environment_piece", "character_base", "material_library"],
    )
    g.add_argument(
        "--style-preset",
        default="toon_bold",
        choices=["realistic_hd_pbr", "anime_stylized", "toon_bold"],
    )
    g.add_argument("--mock", action="store_true", help="Deterministic spec without Ollama")
    g.add_argument("--out", help="Write JSON file (spec + meta); default: stdout spec only")
    g.set_defaults(func=_cmd_generate_spec)

    v = sub.add_parser("validate-spec", help="Validate a JSON file")
    v.add_argument("--file", required=True)
    v.set_defaults(func=_cmd_validate_spec)

    p = sub.add_parser("pack", help="Write Unity-oriented pack folder from a spec JSON file")
    p.add_argument("--spec", required=True, help="Spec JSON or generate-spec output with 'spec' key")
    p.add_argument("--output", required=True, help="Output directory")
    p.add_argument(
        "--unity-urp",
        default="6000.0.x LTS (pin when smoke-tested)",
        dest="unity_urp",
        help="URP version hint for UnityImportNotes.md",
    )
    p.set_defaults(func=_cmd_pack)

    s = sub.add_parser("serve", help="Run HTTP API for the web UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8787)
    s.add_argument("--reload", action="store_true")
    s.set_defaults(func=_cmd_serve)

    q = sub.add_parser(
        "queue-worker",
        help="Poll SQLite job queue and run studio jobs (durable; multiple processes supported)",
    )
    q.add_argument(
        "--worker-id",
        default="cli-worker",
        help="Identifier stored on claimed rows (default: cli-worker)",
    )
    q.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds to sleep when no pending jobs (default: 1)",
    )
    q.add_argument(
        "--once",
        action="store_true",
        help="Process at most one job then exit (or exit immediately if queue empty)",
    )
    q.set_defaults(func=_cmd_queue_worker)

    j = sub.add_parser("run-job", help="Generate spec, write pack under output/jobs, optional ComfyUI textures, zip")
    j.add_argument("--prompt", required=True)
    j.add_argument(
        "--category",
        default="prop",
        choices=["prop", "environment_piece", "character_base", "material_library"],
    )
    j.add_argument(
        "--style-preset",
        default="toon_bold",
        choices=["realistic_hd_pbr", "anime_stylized", "toon_bold"],
    )
    j.add_argument("--mock", action="store_true")
    j.add_argument("--textures", action="store_true", help="Run ComfyUI albedo passes (requires ComfyUI)")
    j.add_argument(
        "--export-mesh",
        action="store_true",
        help="Run headless Blender to emit placeholder GLB (needs Blender or STUDIO_BLENDER_BIN)",
    )
    j.add_argument(
        "--unity-urp",
        default="6000.0.x LTS (pin when smoke-tested)",
        dest="unity_urp",
    )
    j.set_defaults(func=_cmd_run_job)

    tns = sub.add_parser(
        "tenants",
        help="Manage indie/SaaS workspaces (SQLite) and API keys — used when API auth is enabled",
    )
    tns_sub = tns.add_subparsers(dest="tenants_action", required=True)

    tc = tns_sub.add_parser("create", help="Create a tenant (small studio / customer workspace)")
    tc.add_argument("--name", required=True)
    tc.add_argument(
        "--tier",
        default="free",
        choices=["free", "indie", "team"],
        help="Subscription tier (server-side limits)",
    )
    tc.set_defaults(func=_cmd_tenants, tenants_action="create")

    tl = tns_sub.add_parser("list", help="List tenants")
    tl.set_defaults(func=_cmd_tenants, tenants_action="list")

    tk = tns_sub.add_parser("issue-key", help="Create an API key for a tenant (shown once)")
    tk.add_argument("--tenant-id", required=True, dest="tenant_id")
    tk.add_argument("--label", default="", help="Optional note (laptop, CI, …)")
    tk.set_defaults(func=_cmd_tenants, tenants_action="issue-key")

    tt = tns_sub.add_parser("set-tier", help="Change a tenant's tier (admin / billing hook placeholder)")
    tt.add_argument("--tenant-id", required=True, dest="tenant_id")
    tt.add_argument("--tier", required=True, choices=["free", "indie", "team"])
    tt.set_defaults(func=_cmd_tenants, tenants_action="set-tier")

    args = parser.parse_args()
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
