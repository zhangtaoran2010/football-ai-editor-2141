# Football AI Editor 2141 — Handoff

> Local project: `/Users/world/Downloads/code/football-ai-editor-2141`
> GitHub: `zhangtaoran2010/football-ai-editor-2141`
> Created: 2026-10-07

## Purpose

Standalone Intel MacBook Pro A2141 variant of Football AI Editor.

It inherits the stable editorial/rendering rules from the M4 project but replaces local MLX/CosyVoice TTS with MiniMax cloud TTS. The M4 project remains separate.

## Target workflow

`URL/local video -> analyze real actions -> draft Chinese commentary -> STOP for approval -> MiniMax full-pass TTS -> mix/duck original soundtrack -> Chinese labels -> final render -> QA -> user acceptance -> delete task workdir`

## Target machine

- MacBook Pro 16-inch 2019 A2141
- Intel x86_64
- 16 GB RAM
- Python 3.11+
- ffmpeg / ffprobe
- yt-dlp
- Git
- internet access for MiniMax

## MiniMax

No haoqin reference audio is used.

Runtime secrets live only in local `.env`. A safe template is `config/minimax-template.txt`.

The A2141 doctor (requiring API key) and real short TTS smoke test have passed. On a newly configured machine, run `football-ai-editor doctor --require-api-key` and a short TTS test before production.

The user's verified endpoint is `https://api.minimaxi.com/v1` with `speech-2.8-hd`. After A/B listening, the user selected `Chinese (Mandarin)_Straightforward_Boy` (`率真弟弟`) with `speed=1.18` and `emotion=happy` as the default football narration profile.

## Durable rules

Read `AGENTS.md` first in every fresh session.

Key rules:
- commentary approval before TTS,
- never identify players from faces alone,
- visible ranking numbers are not read aloud by default,
- result wording follows visible action,
- one continuous TTS pass for short narration,
- original audio stays quietly underneath with smooth ducking,
- preserve ranked vertical layout when applicable,
- explicit final acceptance before cleanup,
- after acceptance keep final MP4 and remove task intermediates.

## Validation boundary

All 12 unit tests passed on the A2141. They cover inherited pipeline behavior and MiniMax request/response handling, not every task-specific alignment/overlay step.

The full agent workflow for `https://www.youtube.com/shorts/ynui4GDkpXQ` passed on the A2141: source download, visual review, commentary approval, continuous MiniMax TTS, narration alignment, stereo ducking mix, Chinese labels, H.264/AAC render and QA. The user accepted the final with `可以了`.

Accepted output: `output/managers-ynui4GDkpXQ-chinese-v1.mp4` (1080x1920, 60 fps). Its entire `work/ynui4GDkpXQ/` workspace was then removed. Task-specific scripts were removed too; this validation does not mean the existing CLI automatically implements the complete editorial workflow.

## Current migration state

Migration to the Intel A2141 is complete; this is no longer the staging Mac.

Incomplete USB-copied Git metadata was reinitialized with explicit user authorization because the project had no commits. Branch: `main`; origin: `https://github.com/zhangtaoran2010/football-ai-editor-2141.git`. `.env`, `work/` and `output/` are confirmed ignored.

At this handoff update, there are still **zero commits and no push**. First commit/push is a separate follow-up requiring user confirmation; do not trigger it from final-video acceptance or documentation updates alone.

See `A2141-VALIDATION.md` for the environment, acceptance evidence and operational fixes (YouTube client fallback, missing text filters, and narration timestamp/non-silence QA). `MIGRATION-TO-A2141.md` remains the migration/setup reference.
