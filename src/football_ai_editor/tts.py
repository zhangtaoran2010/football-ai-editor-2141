from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "https://api.minimaxi.com/v1"
DEFAULT_MODEL = "speech-2.8-hd"
DEFAULT_VOICE_ID = "Chinese (Mandarin)_Straightforward_Boy"
DEFAULT_SPEED = 1.18
DEFAULT_EMOTION = "happy"


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load a tiny KEY=VALUE .env file without adding a dependency."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class MiniMaxSettings:
    api_key: str
    api_base: str = DEFAULT_API_BASE
    model: str = DEFAULT_MODEL
    voice_id: str = DEFAULT_VOICE_ID
    speed: float = DEFAULT_SPEED
    vol: float = 1.0
    pitch: int = 0
    emotion: str = DEFAULT_EMOTION
    language_boost: str = "Chinese"


def settings_from_env(*, require_api_key: bool = True) -> MiniMaxSettings:
    load_dotenv()
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if require_api_key and not api_key:
        raise RuntimeError(
            "MINIMAX_API_KEY is missing. Copy config/minimax-template.txt to .env and set the key locally."
        )
    return MiniMaxSettings(
        api_key=api_key,
        api_base=os.getenv("MINIMAX_API_BASE", DEFAULT_API_BASE).strip() or DEFAULT_API_BASE,
        model=os.getenv("MINIMAX_TTS_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        voice_id=os.getenv("MINIMAX_VOICE_ID", DEFAULT_VOICE_ID).strip() or DEFAULT_VOICE_ID,
        speed=float(os.getenv("MINIMAX_TTS_SPEED", str(DEFAULT_SPEED))),
        vol=float(os.getenv("MINIMAX_TTS_VOL", "1.0")),
        pitch=int(os.getenv("MINIMAX_TTS_PITCH", "0")),
        emotion=os.getenv("MINIMAX_TTS_EMOTION", DEFAULT_EMOTION).strip(),
        language_boost=os.getenv("MINIMAX_LANGUAGE_BOOST", "Chinese").strip() or "Chinese",
    )


def build_payload(
    text: str,
    settings: MiniMaxSettings,
    *,
    model: str | None = None,
    voice_id: str | None = None,
    speed: float | None = None,
    vol: float | None = None,
    pitch: int | None = None,
    emotion: str | None = None,
) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("Narration text is empty")
    if len(text) >= 10_000:
        raise ValueError("MiniMax synchronous TTS text must be under 10,000 characters")

    selected_speed = settings.speed if speed is None else speed
    selected_vol = settings.vol if vol is None else vol
    selected_pitch = settings.pitch if pitch is None else pitch
    if not 0.5 <= selected_speed <= 2.0:
        raise ValueError("TTS speed must be between 0.5 and 2.0")
    if not 0 < selected_vol <= 10:
        raise ValueError("TTS volume must be greater than 0 and no more than 10")

    voice_setting: dict[str, Any] = {
        "voice_id": voice_id or settings.voice_id,
        "speed": selected_speed,
        "vol": selected_vol,
        "pitch": selected_pitch,
    }
    selected_emotion = settings.emotion if emotion is None else emotion
    if selected_emotion:
        voice_setting["emotion"] = selected_emotion

    return {
        "model": model or settings.model,
        "text": text,
        "stream": False,
        "voice_setting": voice_setting,
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
        "language_boost": settings.language_boost,
        "subtitle_enable": False,
        "output_format": "hex",
    }


def synthesize_to_file(
    text: str,
    output: Path,
    *,
    model: str | None = None,
    voice_id: str | None = None,
    speed: float | None = None,
    vol: float | None = None,
    pitch: int | None = None,
    emotion: str | None = None,
    timeout: float = 120.0,
) -> tuple[Path, dict[str, Any]]:
    settings = settings_from_env(require_api_key=True)
    payload = build_payload(
        text,
        settings,
        model=model,
        voice_id=voice_id,
        speed=speed,
        vol=vol,
        pitch=pitch,
        emotion=emotion,
    )
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = f"{settings.api_base.rstrip('/')}/t2a_v2"
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"MiniMax TTS HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MiniMax TTS network error: {exc.reason}") from exc

    base_resp = response_payload.get("base_resp", {})
    status_code = int(base_resp.get("status_code", 0))
    if status_code != 0:
        raise RuntimeError(
            f"MiniMax TTS API error {status_code}: {base_resp.get('status_msg', 'unknown error')}"
        )

    audio_hex = response_payload.get("data", {}).get("audio", "")
    if not audio_hex:
        raise RuntimeError("MiniMax TTS response did not contain audio data")
    try:
        audio = bytes.fromhex(audio_hex)
    except ValueError as exc:
        raise RuntimeError("MiniMax TTS returned invalid hex audio") from exc
    if not audio:
        raise RuntimeError("MiniMax TTS returned empty audio")

    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output.with_name(output.name + ".tmp")
    tmp_output.write_bytes(audio)
    tmp_output.replace(output)

    metadata = dict(response_payload.get("extra_info", {}))
    metadata["model"] = payload["model"]
    metadata["voice_id"] = payload["voice_setting"]["voice_id"]
    metadata["trace_id"] = response_payload.get("trace_id")
    return output, metadata
