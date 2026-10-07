# Football AI Editor 2141 — Agent Instructions

## Purpose

This repository is the Intel MacBook Pro A2141 version of Football AI Editor.

Target machine:
- MacBook Pro 16-inch (2019), model A2141
- Intel x86_64
- 16 GB RAM
- macOS

The user should normally only need to say:

`处理这个视频：https://...`

or provide a local video path. The agent owns routine technical execution. The user owns editorial approval and final acceptance.

## Default workflow

`source/URL -> acquire -> probe -> inspect real action timeline -> identify names from evidence -> draft complete Chinese commentary -> STOP for approval -> MiniMax full-pass TTS -> align narration -> low-volume original soundtrack + smooth ducking -> concise Chinese labels -> render -> visual/audio QA -> user accepts -> delete task workdir`

Do not reduce editorial understanding to scene cuts or audio peaks. Those are discovery signals only.

## Mandatory commentary approval gate

For every new video:
1. inspect/probe the source,
2. understand the real visual/action timeline,
3. draft the complete Chinese commentary,
4. show the commentary and important timing to the user,
5. STOP,
6. wait for explicit approval such as `文案确认`, `可以，生成`, or equivalent,
7. only after approval generate TTS, mix, labels, final render and QA.

The initial request `处理这个视频` is not TTS approval.

If approved wording later changes materially, re-approve unless the user directly supplied the replacement wording.

## Identity and factual evidence

Never guess a player or manager from appearance.

Names may come from visible on-screen text, source title/metadata, reliable public sources, or explicit user confirmation.

If a material identity/event fact is still ambiguous after inspection, ask one focused question instead of inventing certainty.

Do not let result words such as 进了、扑出、打偏、打高 appear before the corresponding visible action.

## Source acquisition

For YouTube URLs, download into `work/<task-id>/source/`.

Prefer 1080p60 when available, MP4 video + M4A audio, no 4K by default, and no 720p when a 1080p source exists.

Probe the downloaded result and record real resolution, fps and duration while the task is active.

Never delete a user-owned local source outside this repository's task workspace.

## MiniMax TTS — A2141 default

This Intel project does not use MLX, local CosyVoice, or the old haoqin reference voice.

Use the MiniMax HTTP TTS integration in this repository:
- model: `speech-2.8-hd`
- API key: local `.env` only
- default API base for this user's key: `https://api.minimaxi.com/v1`
- user-selected default voice: `Chinese (Mandarin)_Straightforward_Boy` (`率真弟弟`)
- default speed: `1.18`
- default emotion: `happy`
- language boost: Chinese
- output: 32 kHz / 128 kbps / mono MP3

The user has explicitly selected `Chinese (Mandarin)_Straightforward_Boy` with `speed=1.18` and `emotion=happy` as the default football narration profile after listening to multiple built-in voices. Keep this as the project default unless the user later changes it. It remains configurable through `.env`.

Generate short-video narration as one continuous TTS request whenever practical.

If total Chinese narration is <=120 seconds, a wording or voice retry should normally regenerate the whole narration rather than patching one separately generated sentence.

It is fine to cut one verified continuous narration file at natural pauses for timeline placement.

After alignment, verify the aligned narration itself is non-silent before rendering. In a sample-delayed continuous mix, normalize its timestamps before final padding/trimming if necessary (for example, `asetpts=N/SR/TB` after `amix`); verify actual cue timing rather than applying this blindly to PTS-only gaps. A valid raw TTS file does not prove that aligned narration survived the filtergraph.

Do not expose, print, commit or push `MINIMAX_API_KEY`.

## Audio mix

Keep the original soundtrack quietly audible by default. Do not use Demucs unless explicitly needed.

Reliable starting point:
- original soundtrack around `volume=0.32`,
- Chinese narration around `volume=1.08`,
- sidechain around `threshold=0.02:ratio=7:attack=60:release=520:knee=5:level_sc=1.35`,
- `amix=normalize=0`,
- limiter,
- final gain adjusted to avoid clipping.
- preserve the source stereo mix when the source is stereo; MiniMax narration may be generated mono, but upmix/resample the narration for mixing rather than collapsing the whole final soundtrack to mono.

The English broadcast should remain atmospheric, not compete with the Chinese narration.

## Ranked vertical compilation layout

When the source already has a top English title and a left-side ranking list:
- keep the English title,
- place the Chinese theme title clearly below the original English title; y≈390 is only a 1080x1920 reference, so scale/reposition for the actual source dimensions and leave a visible gap rather than mechanically reusing that coordinate,
- keep the left ranking list,
- put concise Chinese person/event labels on the right,
- use approximate lower-to-higher anchors 1470, 1395, 1320, 1245, 1170,
- reveal right-side labels progressively and cumulatively,
- use white text with a black outline,
- avoid generic bottom-center subtitle boxes.

Do not read ranking numbers aloud when they are already clearly visible.

For recurring ranked-series formats, do not editorialize a structurally omitted rank (for example, "第1名没揭晓") unless the source itself explicitly comments on that omission or the user asks for it. Treat repeated series structure as intentional format, not as a missing result.

For non-ranked videos, use the simplest readable layout.

Check available FFmpeg text filters before choosing a rendering path. If `drawtext`/`ass`/`subtitles` are unavailable, macOS Swift/AppKit can generate transparent Chinese text PNGs for `overlay`; inspect font weight, outline, alpha and final frames. Do not require Pillow or rebuild FFmpeg merely for simple labels. See `A2141-VALIDATION.md` for the tested fallback.

## Delivery

For a good portrait 1080p source, final delivery should normally be 1080x1920, 60 fps when source supports it, H.264 around 10 Mbps, and AAC around 192 kbps.

Do not upscale a lower-resolution source merely to claim 1080p.

## QA

Before presenting a final candidate:
- verify the MP4 exists and is readable,
- inspect representative frames and important overlays,
- check no label overlaps/cropping,
- verify narration/result timing against visible action,
- confirm narration is audible and original soundtrack is lower beneath it,
- verify each narration section actually exists in the decoded final MP4; original audio alone can conceal missing narration, so total-track volume or decode success is insufficient,
- check for clipping, silence, obvious sync drift or broken audio.

Automated QA is not final user acceptance. Do not describe objective audio measurements as human listening or speech-content verification.

## Cleanup

Keep the complete task workspace during revisions.

Only after explicit final acceptance such as `可以了`, `最终版确认`, or `就这样`:
1. verify the accepted final MP4 under `output/`,
2. verify no revision is pending,
3. delete that task's entire `work/<task-id>/`,
4. keep the accepted final MP4.

Delete task-specific downloads, frames, TTS, cue files, temporary mixes, render scripts, logs, manifests and QA screenshots.

Never delete repository code/rules, the local `.env`, or a user-owned source outside the task workspace.

## Runtime and engineering discipline

Use Python 3.11+ and existing FFmpeg/ffprobe/yt-dlp.

On Intel Homebrew, binaries commonly live under `/usr/local/bin`. The code also tolerates `/opt/homebrew/bin`.

Run `football-ai-editor doctor --require-api-key` before the first real production task on a newly configured A2141.

Prefer simple file-based execution. Do not introduce unnecessary services, databases, orchestration layers, face recognition, OCR infrastructure, Demucs, or patch-heavy TTS workflows.

Repository rules are the durable source of truth. When a user correction reveals a reusable rule, update the repository rather than relying on chat memory.
