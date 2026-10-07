from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .media import (
    concat_clips,
    detect_scene_times,
    extract_frame,
    probe_video,
    render_clip,
    sample_audio_rms,
    choose_audio_peaks,
)


@dataclass(frozen=True)
class Candidate:
    time: float
    scene: bool = False
    audio_rms: float | None = None


def merge_candidate_signals(
    scene_times: list[float],
    audio_peaks: list[tuple[float, float]],
    *,
    merge_distance: float = 3.0,
) -> list[Candidate]:
    merged: list[Candidate] = []

    for time_s in scene_times:
        merged.append(Candidate(time=time_s, scene=True))

    for time_s, rms in audio_peaks:
        nearest_index = None
        nearest_distance = None
        for index, candidate in enumerate(merged):
            distance = abs(candidate.time - time_s)
            if distance <= merge_distance and (
                nearest_distance is None or distance < nearest_distance
            ):
                nearest_index = index
                nearest_distance = distance
        if nearest_index is None:
            merged.append(Candidate(time=time_s, audio_rms=rms))
        else:
            current = merged[nearest_index]
            merged[nearest_index] = Candidate(
                time=(current.time + time_s) / 2.0,
                scene=True,
                audio_rms=rms,
            )

    return sorted(merged, key=lambda item: item.time)


def _fallback_candidates(duration: float) -> list[Candidate]:
    if duration <= 0:
        return [Candidate(time=0.0)]
    if duration <= 30:
        return [Candidate(time=duration / 2.0)]
    step = 45.0
    times = []
    t = min(15.0, duration / 2.0)
    while t < duration:
        times.append(t)
        t += step
    return [Candidate(time=value) for value in times[:12]]


def _limit_candidates(candidates: list[Candidate], limit: int = 24) -> list[Candidate]:
    if len(candidates) <= limit:
        return sorted(candidates, key=lambda item: item.time)

    with_audio = sorted(
        [candidate for candidate in candidates if candidate.audio_rms is not None],
        key=lambda item: item.audio_rms if item.audio_rms is not None else -120.0,
        reverse=True,
    )
    selected = with_audio[: min(16, limit)]
    selected_times = {candidate.time for candidate in selected}

    remaining = [
        candidate for candidate in candidates if candidate.time not in selected_times
    ]
    slots = limit - len(selected)
    if slots > 0 and remaining:
        if len(remaining) <= slots:
            selected.extend(remaining)
        else:
            step = len(remaining) / slots
            indexes = [min(len(remaining) - 1, int(i * step)) for i in range(slots)]
            selected.extend(remaining[index] for index in indexes)

    deduped = {candidate.time: candidate for candidate in selected}
    return sorted(deduped.values(), key=lambda item: item.time)[:limit]


def candidate_importance(candidate: Candidate, audio_rank: dict[float, int]) -> int:
    score = 4
    if candidate.scene:
        score += 2
    if candidate.audio_rms is not None:
        score += min(3, max(1, 4 - audio_rank.get(candidate.time, 3)))
    return min(10, score)


def prepare(video: Path, workdir: Path) -> tuple[Path, Path]:
    workdir.mkdir(parents=True, exist_ok=True)
    analysis_dir = workdir / "analysis"
    frames_dir = analysis_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    metadata = probe_video(video)
    (workdir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    scene_times = detect_scene_times(video)
    audio_samples = sample_audio_rms(video) if metadata["has_audio"] else []
    audio_peaks = choose_audio_peaks(audio_samples)
    candidates = merge_candidate_signals(scene_times, audio_peaks)
    if not candidates:
        candidates = _fallback_candidates(float(metadata["duration"]))

    # Keep a bounded, reviewable set without biasing toward only the start of the video.
    candidates = _limit_candidates(candidates, limit=24)
    ranked_audio = sorted(
        [c for c in candidates if c.audio_rms is not None],
        key=lambda c: c.audio_rms if c.audio_rms is not None else -120.0,
        reverse=True,
    )
    audio_rank = {c.time: rank for rank, c in enumerate(ranked_audio, start=1)}

    manifest: dict[str, Any] = {
        "video": metadata,
        "review_instructions": (
            "Inspect the candidate frames. Refine events.json so each retained event "
            "covers a meaningful football moment and importance reflects editorial value."
        ),
        "candidates": [],
    }
    events: list[dict[str, Any]] = []
    duration = float(metadata["duration"])
    last_frame_time = max(0.0, duration - 0.05)

    for index, candidate in enumerate(candidates, start=1):
        event_id = f"event-{index:03d}"
        center = max(0.0, min(last_frame_time, candidate.time))
        start = max(0.0, center - 6.0)
        end = min(duration, center + 8.0)
        frame_times = [
            max(0.0, center - 2.0),
            center,
            min(last_frame_time, center + 2.0),
        ]
        frame_paths: list[str] = []
        for frame_index, frame_time in enumerate(frame_times, start=1):
            frame_path = frames_dir / f"{event_id}-{frame_index}.png"
            extract_frame(video, frame_time, frame_path)
            frame_paths.append(str(frame_path.relative_to(workdir)))

        importance = candidate_importance(candidate, audio_rank)
        evidence = {
            "scene_change": candidate.scene,
            "audio_rms_db": candidate.audio_rms,
        }
        manifest["candidates"].append(
            {
                "id": event_id,
                "center": round(center, 3),
                "window": [round(start, 3), round(end, 3)],
                "evidence": evidence,
                "frames": frame_paths,
            }
        )
        events.append(
            {
                "id": event_id,
                "start": round(start, 3),
                "end": round(end, 3),
                "type": "candidate",
                "description": "Heuristic candidate; requires agent visual review.",
                "importance": importance,
                "source": "heuristic",
                "evidence": evidence,
            }
        )

    manifest_path = analysis_dir / "manifest.json"
    events_path = workdir / "events.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    events_path.write_text(
        json.dumps({"events": events}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path, events_path


def merge_overlapping_clips(
    clips: list[dict[str, Any]],
    *,
    gap: float = 1.0,
) -> list[dict[str, Any]]:
    if not clips:
        return []
    ordered = sorted(clips, key=lambda item: float(item["start"]))
    merged = [dict(ordered[0])]
    for clip in ordered[1:]:
        previous = merged[-1]
        if float(clip["start"]) <= float(previous["end"]) + gap:
            previous["end"] = max(float(previous["end"]), float(clip["end"]))
            previous["importance"] = max(
                int(previous.get("importance", 0)),
                int(clip.get("importance", 0)),
            )
            previous["event_ids"] = list(
                dict.fromkeys(
                    list(previous.get("event_ids", []))
                    + list(clip.get("event_ids", []))
                )
            )
        else:
            merged.append(dict(clip))
    return merged


def build_plan(
    events_path: Path,
    output: Path,
    *,
    max_clips: int = 8,
    min_importance: int = 5,
    max_total_duration: float = 120.0,
) -> Path:
    payload = json.loads(events_path.read_text(encoding="utf-8"))
    events = payload.get("events", payload if isinstance(payload, list) else [])
    selected = [
        event
        for event in events
        if int(event.get("importance", 0)) >= min_importance
        and float(event.get("end", 0)) > float(event.get("start", 0))
    ]
    selected.sort(
        key=lambda event: (
            int(event.get("importance", 0)),
            float(event.get("end", 0)) - float(event.get("start", 0)),
        ),
        reverse=True,
    )
    selected = selected[:max_clips]

    clips = [
        {
            "start": float(event["start"]),
            "end": float(event["end"]),
            "importance": int(event.get("importance", 0)),
            "event_ids": [str(event.get("id", "unknown"))],
        }
        for event in selected
    ]
    clips = merge_overlapping_clips(clips)

    # Preserve source chronology while respecting the duration cap.
    clips.sort(key=lambda clip: float(clip["start"]))
    bounded: list[dict[str, Any]] = []
    used = 0.0
    for clip in clips:
        duration = float(clip["end"]) - float(clip["start"])
        if used >= max_total_duration:
            break
        if used + duration > max_total_duration:
            clip = dict(clip)
            clip["end"] = float(clip["start"]) + (max_total_duration - used)
            duration = float(clip["end"]) - float(clip["start"])
        if duration > 0.25:
            bounded.append(clip)
            used += duration

    plan = {
        "version": "0.1",
        "clips": bounded,
        "total_duration": round(used, 3),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def render(video: Path, plan_path: Path, output: Path, workdir: Path) -> Path:
    metadata = probe_video(video)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    clips = plan.get("clips", [])
    if not clips:
        raise ValueError("Edit plan contains no clips")

    temp_dir = workdir / "render-clips"
    temp_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for index, clip in enumerate(clips, start=1):
        clip_path = temp_dir / f"clip-{index:03d}.mp4"
        render_clip(
            video,
            float(clip["start"]),
            float(clip["end"]),
            clip_path,
            has_audio=bool(metadata["has_audio"]),
            width=metadata.get("width"),
            height=metadata.get("height"),
            fps=metadata.get("fps"),
        )
        rendered.append(clip_path)

    concat_clips(rendered, output)
    return output
