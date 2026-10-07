from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any




DEFAULT_PORTRAIT_WIDTH = 1080
DEFAULT_PORTRAIT_HEIGHT = 1920
DEFAULT_PORTRAIT_BITRATE = "10M"
DEFAULT_OTHER_BITRATE = "6M"


def delivery_video_profile(
    width: int | None,
    height: int | None,
    fps: float | None = None,
) -> dict[str, Any]:
    """Return the default delivery profile without pointless upscaling.

    Portrait sources at or above 1080 px wide are capped at 1080 px wide.
    A normal 9:16 source therefore delivers at 1080x1920. Lower-resolution
    portrait sources are kept at source resolution rather than being upscaled.
    """
    if not width or not height:
        return {"video_filter": None, "bitrate": DEFAULT_OTHER_BITRATE}

    if height > width and width >= DEFAULT_PORTRAIT_WIDTH:
        video_filter = None
        if width != DEFAULT_PORTRAIT_WIDTH:
            video_filter = f"scale={DEFAULT_PORTRAIT_WIDTH}:-2"
        return {
            "video_filter": video_filter,
            "bitrate": DEFAULT_PORTRAIT_BITRATE,
            "target_width": DEFAULT_PORTRAIT_WIDTH,
            "target_height": (
                DEFAULT_PORTRAIT_HEIGHT
                if width * DEFAULT_PORTRAIT_HEIGHT == height * DEFAULT_PORTRAIT_WIDTH
                else None
            ),
            "fps": fps,
        }

    return {
        "video_filter": None,
        "bitrate": DEFAULT_OTHER_BITRATE,
        "target_width": width,
        "target_height": height,
        "fps": fps,
    }

COMMON_BIN_DIRS = (
    Path("/opt/homebrew/bin"),
    Path("/usr/local/bin"),
)


def find_binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for directory in COMMON_BIN_DIRS:
        candidate = directory / name
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(
        f"Required executable '{name}' was not found in PATH or common Homebrew locations."
    )


def run_checked(args: list[str], *, capture_stderr: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
    )


def probe_video(video: Path) -> dict[str, Any]:
    ffprobe = find_binary("ffprobe")
    proc = run_checked(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(video),
        ]
    )
    raw = json.loads(proc.stdout)
    streams = raw.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(
        raw.get("format", {}).get("duration")
        or video_stream.get("duration")
        or 0.0
    )

    def parse_rate(value: str | None) -> float | None:
        if not value or value == "0/0":
            return None
        if "/" in value:
            n, d = value.split("/", 1)
            d_float = float(d)
            return float(n) / d_float if d_float else None
        return float(value)

    return {
        "path": str(video.resolve()),
        "duration": duration,
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": parse_rate(video_stream.get("avg_frame_rate")),
        "video_codec": video_stream.get("codec_name"),
        "has_audio": audio_stream is not None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
    }


_SCENE_TIME_RE = re.compile(r"pts_time:([0-9.]+)")


def detect_scene_times(video: Path, threshold: float = 0.32) -> list[float]:
    ffmpeg = find_binary("ffmpeg")
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode not in (0,):
        return []
    values: list[float] = []
    for match in _SCENE_TIME_RE.finditer(proc.stderr):
        value = float(match.group(1))
        if not values or abs(value - values[-1]) > 0.4:
            values.append(value)
    return values


_AUDIO_FRAME_RE = re.compile(r"frame:\d+\s+pts:\S+\s+pts_time:([0-9.]+)")
_AUDIO_RMS_RE = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?(?:inf|[0-9.]+))")


def sample_audio_rms(video: Path) -> list[tuple[float, float]]:
    ffmpeg = find_binary("ffmpeg")
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-vn",
            "-af",
            "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
            "-f",
            "null",
            "-",
        ],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return []

    samples: list[tuple[float, float]] = []
    pending_time: float | None = None
    for line in proc.stderr.splitlines():
        frame_match = _AUDIO_FRAME_RE.search(line)
        if frame_match:
            pending_time = float(frame_match.group(1))
            continue
        rms_match = _AUDIO_RMS_RE.search(line)
        if rms_match and pending_time is not None:
            raw = rms_match.group(1)
            rms = -120.0 if raw == "-inf" else float(raw)
            samples.append((pending_time, rms))
            pending_time = None
    return samples


def choose_audio_peaks(
    samples: list[tuple[float, float]],
    *,
    max_peaks: int = 16,
    min_separation: float = 6.0,
) -> list[tuple[float, float]]:
    if not samples:
        return []
    finite = [value for _, value in samples if math.isfinite(value)]
    if not finite:
        return []
    ordered = sorted(samples, key=lambda item: item[1], reverse=True)
    selected: list[tuple[float, float]] = []
    for time_s, rms in ordered:
        if all(abs(time_s - t) >= min_separation for t, _ in selected):
            selected.append((time_s, rms))
            if len(selected) >= max_peaks:
                break
    return sorted(selected)


def extract_frame(video: Path, at: float, output: Path, height: int = 720) -> None:
    ffmpeg = find_binary("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, at):.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            f"scale=-2:{height}",
            "-y",
            str(output),
        ],
        check=True,
    )


def has_encoder(name: str) -> bool:
    ffmpeg = find_binary("ffmpeg")
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return name in proc.stdout


def render_clip(
    video: Path,
    start: float,
    end: float,
    output: Path,
    *,
    has_audio: bool,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
) -> None:
    ffmpeg = find_binary("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)
    encoder = "h264_videotoolbox" if has_encoder("h264_videotoolbox") else "libx264"
    profile = delivery_video_profile(width, height, fps)
    args = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, start):.3f}",
        "-to",
        f"{max(start + 0.1, end):.3f}",
        "-i",
        str(video),
        "-c:v",
        encoder,
    ]
    if profile["video_filter"]:
        args.extend(["-vf", str(profile["video_filter"])])
    if encoder == "h264_videotoolbox":
        args.extend(["-b:v", str(profile["bitrate"])])
    else:
        args.extend(["-preset", "veryfast", "-crf", "19" if profile["bitrate"] == DEFAULT_PORTRAIT_BITRATE else "21"])
    if has_audio:
        args.extend(["-c:a", "aac", "-b:a", "160k"])
    else:
        args.append("-an")
    args.extend(["-movflags", "+faststart", "-y", str(output)])
    subprocess.run(args, check=True)


def concat_clips(clips: list[Path], output: Path) -> None:
    if not clips:
        raise ValueError("No clips to concatenate")
    ffmpeg = find_binary("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)
    concat_file = output.parent / f".{output.stem}-concat.txt"
    concat_file.write_text(
        "".join(f"file '{clip.resolve()}'\n" for clip in clips),
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                "-y",
                str(output),
            ],
            check=True,
        )
    finally:
        concat_file.unlink(missing_ok=True)
