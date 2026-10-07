from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .doctor import run_doctor
from .pipeline import build_plan, prepare, render
from .review import create_review_pack
from .tts import synthesize_to_file


def _video_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"Video file not found: {path}")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="football-ai-editor",
        description="Football AI editor for Intel MacBook Pro A2141",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_cmd = sub.add_parser("doctor", help="Check the A2141 runtime and MiniMax configuration")
    doctor_cmd.add_argument("--require-api-key", action="store_true")

    tts_cmd = sub.add_parser("tts", help="Generate one continuous MiniMax narration file")
    text_group = tts_cmd.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text")
    text_group.add_argument("--text-file", type=Path)
    tts_cmd.add_argument("--output", type=Path, required=True)
    tts_cmd.add_argument("--model")
    tts_cmd.add_argument("--voice-id")
    tts_cmd.add_argument("--speed", type=float)
    tts_cmd.add_argument("--vol", type=float)
    tts_cmd.add_argument("--pitch", type=int)
    tts_cmd.add_argument("--emotion")

    prepare_cmd = sub.add_parser("prepare", help="Probe video and prepare candidate frames/events")
    prepare_cmd.add_argument("video", type=_video_path)
    prepare_cmd.add_argument("--workdir", type=Path, default=Path("work/latest"))

    agent_prepare_cmd = sub.add_parser(
        "agent-prepare",
        help="Prepare heuristic candidates plus a dense visual review pack for an agent",
    )
    agent_prepare_cmd.add_argument("video", type=_video_path)
    agent_prepare_cmd.add_argument("--workdir", type=Path, default=Path("work/latest"))
    agent_prepare_cmd.add_argument("--min-importance", type=int, default=5)

    review_pack_cmd = sub.add_parser(
        "review-pack",
        help="Create or refresh an agent visual review pack for an events file",
    )
    review_pack_cmd.add_argument("video", type=_video_path)
    review_pack_cmd.add_argument("--events", type=Path, required=True)
    review_pack_cmd.add_argument("--workdir", type=Path, default=Path("work/latest"))
    review_pack_cmd.add_argument("--min-importance", type=int, default=5)

    plan_cmd = sub.add_parser("plan", help="Build deterministic edit plan from events.json")
    plan_cmd.add_argument("--events", type=Path, required=True)
    plan_cmd.add_argument("--output", type=Path, required=True)
    plan_cmd.add_argument("--max-clips", type=int, default=8)
    plan_cmd.add_argument("--min-importance", type=int, default=5)
    plan_cmd.add_argument("--max-total-duration", type=float, default=120.0)

    render_cmd = sub.add_parser("render", help="Render MP4 from edit plan")
    render_cmd.add_argument("video", type=_video_path)
    render_cmd.add_argument("--plan", type=Path, required=True)
    render_cmd.add_argument("--output", type=Path, required=True)
    render_cmd.add_argument("--workdir", type=Path, default=Path("work/latest"))

    finalize_cmd = sub.add_parser(
        "finalize",
        help="Build the final plan and render from agent-reviewed semantic events",
    )
    finalize_cmd.add_argument("video", type=_video_path)
    finalize_cmd.add_argument("--events", type=Path, required=True)
    finalize_cmd.add_argument("--workdir", type=Path, default=Path("work/latest"))
    finalize_cmd.add_argument("--output", type=Path, default=Path("output/highlight-final.mp4"))
    finalize_cmd.add_argument("--max-clips", type=int, default=8)
    finalize_cmd.add_argument("--min-importance", type=int, default=7)
    finalize_cmd.add_argument("--max-total-duration", type=float, default=60.0)

    run_cmd = sub.add_parser("run", help="Prepare, plan, and render using heuristic events")
    run_cmd.add_argument("video", type=_video_path)
    run_cmd.add_argument("--workdir", type=Path, default=Path("work/latest"))
    run_cmd.add_argument("--output", type=Path, default=Path("output/highlight-v01.mp4"))
    run_cmd.add_argument("--max-clips", type=int, default=8)
    run_cmd.add_argument("--min-importance", type=int, default=5)
    run_cmd.add_argument("--max-total-duration", type=float, default=120.0)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "doctor":
        return run_doctor(require_api_key=args.require_api_key)

    if args.command == "tts":
        text = args.text
        if args.text_file is not None:
            text = args.text_file.expanduser().read_text(encoding="utf-8").strip()
        output, metadata = synthesize_to_file(
            text or "",
            args.output,
            model=args.model,
            voice_id=args.voice_id,
            speed=args.speed,
            vol=args.vol,
            pitch=args.pitch,
            emotion=args.emotion,
        )
        print(json.dumps({"output": str(output), "metadata": metadata}, ensure_ascii=False))
        return 0

    if args.command == "prepare":
        manifest, events = prepare(args.video, args.workdir)
        print(json.dumps({"manifest": str(manifest), "events": str(events)}, ensure_ascii=False))
        return 0

    if args.command == "agent-prepare":
        manifest, events = prepare(args.video, args.workdir)
        review_pack = create_review_pack(
            args.video,
            events,
            args.workdir,
            min_importance=args.min_importance,
        )
        print(json.dumps(
            {"manifest": str(manifest), "events": str(events), "review_pack": str(review_pack)},
            ensure_ascii=False,
        ))
        return 0

    if args.command == "review-pack":
        review_pack = create_review_pack(
            args.video,
            args.events,
            args.workdir,
            min_importance=args.min_importance,
        )
        print(review_pack)
        return 0

    if args.command == "plan":
        plan = build_plan(
            args.events,
            args.output,
            max_clips=args.max_clips,
            min_importance=args.min_importance,
            max_total_duration=args.max_total_duration,
        )
        print(plan)
        return 0

    if args.command == "render":
        output = render(args.video, args.plan, args.output, args.workdir)
        print(output)
        return 0

    if args.command == "finalize":
        plan = args.workdir / "edit-plan-final.json"
        build_plan(
            args.events,
            plan,
            max_clips=args.max_clips,
            min_importance=args.min_importance,
            max_total_duration=args.max_total_duration,
        )
        output = render(args.video, plan, args.output, args.workdir)
        print(json.dumps({"plan": str(plan), "output": str(output)}, ensure_ascii=False))
        return 0

    if args.command == "run":
        _, events = prepare(args.video, args.workdir)
        plan = args.workdir / "edit-plan.json"
        build_plan(
            events,
            plan,
            max_clips=args.max_clips,
            min_importance=args.min_importance,
            max_total_duration=args.max_total_duration,
        )
        output = render(args.video, plan, args.output, args.workdir)
        print(output)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
