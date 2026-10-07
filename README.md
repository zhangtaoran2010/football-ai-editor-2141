# Football AI Editor 2141

Standalone Intel-Mac version of the user's Football AI Editor workflow.

Repository: `zhangtaoran2010/football-ai-editor-2141`

## Target

- MacBook Pro 16-inch (2019), A2141
- Intel x86_64
- 16 GB RAM
- macOS
- Python 3.11+
- FFmpeg / ffprobe
- yt-dlp
- MiniMax cloud TTS

This version deliberately does **not** depend on MLX, local CosyVoice, or the previous haoqin reference voice.

## Workflow

`YouTube URL / local video -> visual/action analysis -> Chinese commentary -> user approval -> TTS -> audio ducking + labels -> final render -> QA -> user acceptance -> task cleanup`

The long-term rules live in `AGENTS.md`.

## First-time setup on the A2141

With Intel Homebrew, tools are typically under `/usr/local/bin`.

```bash
brew install python@3.11 ffmpeg yt-dlp git
```

Clone and install:

```bash
git clone https://github.com/zhangtaoran2010/football-ai-editor-2141.git
cd football-ai-editor-2141
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

Configure MiniMax locally:

```bash
# Keep an existing configured .env intact.
[ -e .env ] || cp config/minimax-template.txt .env
```

Edit `.env` and fill in `MINIMAX_API_KEY`. The real `.env` is ignored by Git and must never be committed.

This project now defaults to the Mainland China MiniMax endpoint `https://api.minimaxi.com/v1`, because that is the endpoint verified with the user's real key. Only switch to `https://api.minimax.io/v1` for an international-platform key.

Run:

```bash
football-ai-editor doctor --require-api-key
```

Or before editable install:

```bash
./scripts/check-environment.sh --require-api-key
```

## MiniMax TTS

Defaults:
- model: `speech-2.8-hd`
- user-selected voice: `Chinese (Mandarin)_Straightforward_Boy` (`率真弟弟`)
- speed: `1.18`
- emotion: `happy`
- Chinese language boost
- 32 kHz, 128 kbps, mono MP3 for the raw narration
- during final mixing, preserve stereo when the source soundtrack is stereo by upmixing/resampling the narration rather than collapsing the final mix to mono

The default voice profile was chosen by the user after A/B listening. It remains configurable in `.env` through `MINIMAX_VOICE_ID`, `MINIMAX_TTS_SPEED`, and `MINIMAX_TTS_EMOTION`.

Smoke test:

```bash
mkdir -p work
football-ai-editor tts \
  --text "这是一段足球短视频解说测试。" \
  --output work/tts-smoke.mp3
```

For a real video, save the approved narration to a UTF-8 text file and generate it in one pass:

```bash
football-ai-editor tts \
  --text-file work/<task-id>/commentary-approved.txt \
  --output work/<task-id>/narration-full.mp3
```

## Agent use

Open Pi/Codex in this repository and let it read `AGENTS.md`.

Normal input:

```text
处理这个视频：https://www.youtube.com/...
```

The agent must stop after drafting the Chinese commentary. TTS/rendering begins only after commentary approval.

## Existing editor helpers

```bash
football-ai-editor agent-prepare /path/to/video.mp4 --workdir work/task
football-ai-editor review-pack /path/to/video.mp4 --events work/task/events-reviewed.json --workdir work/task
football-ai-editor finalize /path/to/video.mp4 --events work/task/events-reviewed.json --workdir work/task --output output/final.mp4
```

These helpers do not replace agent visual/editorial judgment.

## Security

Never commit the local `.env`, MiniMax API key, downloaded videos, generated audio, task workdirs or final media. Git should contain code, rules, tests and configuration templates only.


## A2141 validation and migration

USB migration to `/Users/world/Downloads/code/football-ai-editor-2141` is complete. The Intel A2141 passed doctor, all 12 unit tests, a real MiniMax smoke test, and one complete video workflow with explicit user acceptance.

See `A2141-VALIDATION.md` for the verified environment and workarounds for YouTube restrictions, missing FFmpeg text filters, and narration alignment/QA. Doctor checks binary availability, not all optional filters. The successful full workflow included task-specific agent scripts; it does not imply the CLI automates every editing step.

At this documentation update, the repository remains on `main` with zero commits and no push. First commit/push will be a separately confirmed step from the A2141.

See `MIGRATION-TO-A2141.md` for reusable setup and migration instructions.
