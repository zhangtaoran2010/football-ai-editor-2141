from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from .media import find_binary, probe_video


def timeline_sample_times(
    start: float,
    end: float,
    *,
    max_frames: int = 12,
) -> list[float]:
    if max_frames < 2:
        raise ValueError("max_frames must be at least 2")
    if end <= start:
        return [max(0.0, start)]

    span = end - start
    count = min(max_frames, max(3, math.ceil(span / 1.5) + 1))
    if count <= 1:
        return [start]
    step = span / (count - 1)
    return [start + step * index for index in range(count)]


def boundary_sample_times(
    boundary: float,
    duration: float,
    *,
    radius: float = 2.0,
    step: float = 1.0,
) -> list[float]:
    if step <= 0:
        raise ValueError("step must be positive")
    first = boundary - radius
    count = int(round((radius * 2) / step)) + 1
    values = [
        min(max(0.0, first + index * step), max(0.0, duration - 0.25))
        for index in range(count)
    ]
    result: list[float] = []
    for value in values:
        rounded = round(value, 3)
        if not result or rounded != result[-1]:
            result.append(rounded)
    return result


def _create_strip(
    video: Path,
    times: list[float],
    output: Path,
    *,
    height: int = 240,
) -> None:
    if not times:
        raise ValueError("No sample times supplied")
    ffmpeg = find_binary("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)

    args = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    for time_s in times:
        args.extend(["-ss", f"{max(0.0, time_s):.3f}", "-i", str(video)])

    filters: list[str] = []
    labels: list[str] = []
    for index in range(len(times)):
        label = f"v{index}"
        filters.append(f"[{index}:v]scale=-2:{height}[{label}]")
        labels.append(f"[{label}]")
    filters.append(f"{''.join(labels)}hstack=inputs={len(times)}[out]")

    args.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-frames:v",
            "1",
            "-y",
            str(output),
        ]
    )
    subprocess.run(args, check=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg completed without creating review image: {output}")


def create_review_pack(
    video: Path,
    events_path: Path,
    workdir: Path,
    *,
    min_importance: int = 5,
    context: float = 2.0,
    max_timeline_frames: int = 12,
) -> Path:
    payload = json.loads(events_path.read_text(encoding="utf-8"))
    events = payload.get("events", payload if isinstance(payload, list) else [])
    metadata = probe_video(video)
    duration = float(metadata["duration"])
    last_frame_time = max(0.0, duration - 0.25)

    review_dir = workdir / "agent-review"
    review_dir.mkdir(parents=True, exist_ok=True)

    selected = [
        event
        for event in events
        if int(event.get("importance", 0)) >= min_importance
        and float(event.get("end", 0)) > float(event.get("start", 0))
    ]

    manifest: dict[str, Any] = {
        "version": "agent-review-pack-v0.3",
        "video": metadata,
        "source_events": str(events_path),
        "editorial_policy": [
            "Classify the real football event, not just visual motion or loud audio.",
            "Merge duplicate candidates and multiple replay angles of the same incident.",
            "Goals should include readable build-up, finish, immediate celebration and at most one useful replay.",
            "Non-goal chances should usually keep live action plus immediate reaction and remove repeated replay angles.",
            "Avoid starting or ending on broadcast dissolves, graphics or other transition frames.",
            "Exclude intro graphics, generic stoppages, outro/subscribe screens and filler unless editorially necessary.",
        ],
        "output_contract": {
            "path_suggestion": str(workdir / "events-reviewed.json"),
            "shape": {
                "events": [
                    {
                        "id": "reviewed-event-id",
                        "start": 0.0,
                        "end": 0.0,
                        "type": "goal|big_chance|save|card|other",
                        "description": "short factual description",
                        "importance": "1-10",
                        "source": "agent-vision-review",
                    }
                ]
            },
        },
        "candidates": [],
    }

    for index, event in enumerate(selected, start=1):
        event_id = str(event.get("id") or f"candidate-{index:03d}")
        start = max(0.0, float(event["start"]))
        end = min(duration, float(event["end"]))
        window_start = max(0.0, min(last_frame_time, start - context))
        window_end = max(window_start, min(last_frame_time, end + context))

        timeline_times = timeline_sample_times(
            window_start,
            window_end,
            max_frames=max_timeline_frames,
        )
        start_times = boundary_sample_times(start, duration)
        end_times = boundary_sample_times(end, duration)

        safe_id = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in event_id
        )
        event_dir = review_dir / safe_id
        timeline_path = event_dir / "timeline.png"
        start_path = event_dir / "start-boundary.png"
        end_path = event_dir / "end-boundary.png"

        _create_strip(video, timeline_times, timeline_path, height=180)
        _create_strip(video, start_times, start_path)
        _create_strip(video, end_times, end_path)

        manifest["candidates"].append(
            {
                "id": event_id,
                "original_event": event,
                "window": [round(window_start, 3), round(window_end, 3)],
                "timeline": {
                    "image": str(timeline_path.relative_to(workdir)),
                    "times_left_to_right": [
                        round(value, 3) for value in timeline_times
                    ],
                },
                "start_boundary": {
                    "image": str(start_path.relative_to(workdir)),
                    "times_left_to_right": start_times,
                },
                "end_boundary": {
                    "image": str(end_path.relative_to(workdir)),
                    "times_left_to_right": end_times,
                },
            }
        )

    manifest_path = review_dir / "review-pack.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path
