from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass

from .tts import load_dotenv


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    required: bool = True


def _binary_check(name: str) -> Check:
    path = shutil.which(name)
    if path:
        return Check(name, "OK", path)
    for candidate in (f"/usr/local/bin/{name}", f"/opt/homebrew/bin/{name}"):
        if os.path.isfile(candidate):
            return Check(name, "OK", candidate)
    return Check(name, "MISSING", "not found", required=True)


def collect_checks(*, require_api_key: bool = False) -> list[Check]:
    load_dotenv()
    machine = platform.machine() or "unknown"
    macos = platform.mac_ver()[0] or "unknown"
    python_ok = sys.version_info >= (3, 11)
    key_present = bool(os.getenv("MINIMAX_API_KEY", "").strip())

    return [
        Check("macOS", "OK" if sys.platform == "darwin" else "WARN", macos, required=False),
        Check(
            "architecture",
            "OK" if machine in {"x86_64", "AMD64"} else "WARN",
            f"{machine}; A2141 target is Intel x86_64",
            required=False,
        ),
        Check("python", "OK" if python_ok else "MISSING", platform.python_version(), required=True),
        _binary_check("git"),
        _binary_check("ffmpeg"),
        _binary_check("ffprobe"),
        _binary_check("yt-dlp"),
        Check(
            "MINIMAX_API_KEY",
            "OK" if key_present else ("MISSING" if require_api_key else "WARN"),
            "configured" if key_present else "not configured; keep it only in local .env",
            required=require_api_key,
        ),
    ]


def run_doctor(*, require_api_key: bool = False) -> int:
    checks = collect_checks(require_api_key=require_api_key)
    for check in checks:
        print(f"{check.status:7} {check.name:16} {check.detail}")
    failed = [check for check in checks if check.required and check.status == "MISSING"]
    if failed:
        print("\nEnvironment is not ready.")
        return 1
    print("\nEnvironment is ready for the requested checks.")
    return 0
