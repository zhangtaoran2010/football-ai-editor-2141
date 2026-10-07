# Migrate to the A2141

Migration and full A2141 workflow acceptance are complete. The current machine is the Intel A2141; see `A2141-VALIDATION.md` for the results and operational fixes. First commit/push remains a separate pending step.

The instructions below document the original staging-to-A2141 USB migration and can be reused for a fresh setup.

Both machines use the same target path:

`/Users/world/Downloads/code/football-ai-editor-2141`

## Before copying from the current Mac

The current Mac is only the staging/test machine.

Before migration:
- do not commit,
- do not push,
- do not copy any real MiniMax key into the repository,
- remove local smoke-test media under `work/` and `output/`,
- keep the source code, docs, tests, `.git` metadata and configured `origin` remote.

The GitHub target is:

`https://github.com/zhangtaoran2010/football-ai-editor-2141.git`

## USB copy

Copy the complete `football-ai-editor-2141` directory to the USB drive, then copy it on the A2141 to:

`/Users/world/Downloads/code/football-ai-editor-2141`

Copy the whole directory so hidden files such as `.git` are preserved.

If `.git` is missing after the copy, recover with:

```bash
cd /Users/world/Downloads/code/football-ai-editor-2141
git init -b main
git remote add origin https://github.com/zhangtaoran2010/football-ai-editor-2141.git
```

If `.git` exists but Git cannot recognize the repository, inspect `HEAD`, `config`, `objects/` and `refs/` before changing it. The actual USB copy lacked `objects/` and `refs/`. Because this project was confirmed to have zero commits, the user authorized deleting the incomplete `.git` and rerunning the initialization above. Never use that deletion shortcut on a repository with history or unknown state.

After recovery, verify `git status`, `git symbolic-ref --short HEAD`, `git remote -v` and `git check-ignore -v .env work/ output/`. Do not commit or push as part of recovery.

## First A2141 setup

From the project directory:

```bash
brew install python@3.11 ffmpeg yt-dlp git
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
# Only create a template if no local .env exists; never overwrite a configured key.
[ -e .env ] || cp config/minimax-template.txt .env
```

Keep the real MiniMax API key only in local `.env`. The user's verified key uses `MINIMAX_API_BASE=https://api.minimaxi.com/v1`. The checked-in template defaults to the user-selected football profile: `Chinese (Mandarin)_Straightforward_Boy`, `speed=1.18`, `emotion=happy`.

Then run:

```bash
football-ai-editor doctor --require-api-key
python -m unittest discover -s tests -v
```

Run a real MiniMax smoke test:

```bash
mkdir -p work
football-ai-editor tts \
  --text "这是一段足球短视频解说测试。" \
  --output work/tts-smoke.mp3
```

Listen to the result before processing a full video.

## Final A2141 acceptance test

Only after the environment check and TTS smoke test pass, process one real short video through the normal project workflow.

Verify:
- YouTube/source acquisition works,
- video probing and frame extraction work,
- commentary approval gate is respected,
- MiniMax returns usable Chinese narration,
- FFmpeg mix/render works,
- final H.264/AAC MP4 is readable,
- visual and audio QA are acceptable.

## Commit and push from the A2141

The first Git commit for this repository should be made on the A2141 after the real-machine validation passes and the user confirms the commit/push step. Validation has passed, but no commit or push has been performed at this documentation update.

Suggested commands:

```bash
git status
git add .
git diff --cached --check
git commit -m "Initialize Football AI Editor for A2141"
git push -u origin main
```

Before committing, confirm that `.env`, `work/`, `output/`, generated audio and media are still ignored.
