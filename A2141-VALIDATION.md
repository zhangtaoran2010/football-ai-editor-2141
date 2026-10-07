# A2141 真机验收与已知问题

## 已完成的验收

当前项目已运行在目标 Intel Mac，而非 M4 staging Mac：
- 路径：`/Users/world/Downloads/code/football-ai-editor-2141`
- 机器：MacBookPro16,1、Intel Core i7-9750H、x86_64、16 GB RAM
- macOS：26.7
- 实际执行 Python：3.11.15
- FFmpeg / ffprobe：8.1.1
- yt-dlp：2026.03.17
- Git：2.50.1

项目 doctor（要求 API Key）、12 项单元测试和 MiniMax 短 TTS 真机测试通过。MiniMax 使用 AGENTS.md 规定的默认配置；没有输出或提交密钥。

实战视频：`https://www.youtube.com/shorts/ynui4GDkpXQ`
- 下载实际规格：1080×1920、60 fps、53.59 秒、原声双声道。
- 完成画面检查、人物文字证据确认、完整中文文案审批。
- 用户回复“确认”后，才生成一条连续 MiniMax 配音并进行时间对齐、原声 ducking、标题和标签、渲染、QA。
- 最终文件：`output/managers-ynui4GDkpXQ-chinese-v1.mp4`
- H.264 1080×1920 60 fps；AAC 48 kHz、192 kbps、双声道。
- 全片解码通过；音频平均 -20.1 dBFS、峰值 -2.2 dBFS，无削波迹象。
- 在旁白活动窗口中，旁白 RMS 比 ducking 后原声高约 17.66 dB。
- 从最终 MP4 解码的音频与对齐旁白在五段中的相关系数均超过 0.95，确认最终文件确实包含各段旁白且无显著样本级漂移。这不是发音识别或主观听感检测。
- 用户明确回复“可以了”，最终接受成片；随后只删除 `work/ynui4GDkpXQ/`，保留最终 MP4。

这是代理执行的完整工作流验收，不代表现有 CLI 已自动实现所有编辑环节。本次使用的任务专用对齐、AppKit 文字和渲染脚本已随任务目录清理；通用 CLI 未修改。12 项单元测试不覆盖这些任务专用步骤。

记录更新时：仓库在 `main`，origin 为 `https://github.com/zhangtaoran2010/football-ai-editor-2141.git`，仍无 commit、未 push。首次 commit/push 是后续单独步骤，不应因成片确认或文档更新而自动执行。

## 1. USB 迁移后的 Git 元数据不完整

现场 `.git/HEAD` 和 `.git/config` 存在，但 `objects/`、`refs/` 缺失，`git status` 返回“not a git repository”。

本项目当时确认没有任何 commit，因此按用户授权删除不完整 `.git`，重新 `git init -b main` 并配置 origin。随后确认 `.env`、`work/`、`output/` 均被忽略。

不要把此恢复方法用于有提交历史或状态不明的仓库；先检查历史与备份，不应为了让 status 成功就删除元数据。

## 2. YouTube 429 / 反机器人限制

默认下载客户端首次返回 HTTP 429 和登录反机器人错误。android/ios 尝试只能看到低清格式，不能因此交付低清或上采样冒充 1080p。

本机已装 Deno；使用 tv/web_embedded 客户端成功列出并下载 1080p60 MP4 + M4A：

```bash
yt-dlp --js-runtimes deno \
  --extractor-args 'youtube:player_client=tv,web_embedded' \
  --no-playlist \
  -f '299+140' \
  --merge-output-format mp4 \
  -o 'work/<task-id>/source/%(id)s.%(ext)s' \
  'https://www.youtube.com/shorts/<id>'
```

`299+140` 是本次视频已验证的格式 ID，不保证跨视频有效。新视频先用 `-F` 检查分辨率和帧率，再选 1080p60 MP4 + M4A；下载后用 ffprobe 核验。竖屏 1080p 是 1080×1920，不要把横屏 1080 高度限制机械套用到 Shorts。

这只是一次已验证的回退路径，不保证长期有效。持续失败时应检查网络限流、yt-dlp 版本和 JS runtime，避免无限重试；账号 cookies 等认证信息仅在需要且用户授权时使用，不输出敏感信息。

## 3. FFmpeg 缺少文字滤镜 / Python 缺少 Pillow

本机 FFmpeg 8.1.1 有 overlay、sidechaincompress，但没有 drawtext、ass、subtitles。Python 3.11 环境也没有 Pillow。doctor 只检查二进制存在，不检查这些滤镜或可选 Python 包，因此 doctor 成功不等于任意文字渲染脚本可用。

先检查：

```bash
ffmpeg -hide_banner -filters
```

本次解决方式：
- 联系表使用 FFmpeg scale + tile，不依赖 Pillow。
- 中文标题和标签用 macOS Swift / AppKit、PingFang SC 生成透明 PNG。
- 白色文字先绘黑色偏移描边、再绘白色填充；最终由 FFmpeg overlay 叠加，并按时间累计显示。
- 没有安装额外服务或重编 FFmpeg。

每个新任务仍须检查字体、透明度、文字边界和最终代表帧。不要把标题/标签位置机械套用到不同源尺寸。

## 4. 配音对齐后的时间戳 / 静音问题（重要）

一次中间混音中，原始 MiniMax MP3 非静音，但经多个 atrim/asetpts/adelay 分支、amix、apad、atrim 后，对齐 WAV 全部为零。原声仍可听、MP4 仍能正常解码，因此仅检查文件存在、解码成功或总音轨峰值，发现不了旁白缺失。

排查定位到本次对齐图中 amix 后的时间戳与末尾 atrim 的组合。对已经用 adelay 生成真实延迟样本的连续混合音轨，在末尾 padding/trimming 前重建连续时间戳，解决了本次问题：

```text
... amix=inputs=<N>:normalize=0,asetpts=N/SR/TB,apad,atrim=duration=<video-duration> ...
```

这不是所有 filtergraph 的无条件修复：如果时间间隙只存在于 PTS 而没有真实静音样本，直接按样本数重建 PTS 可能破坏时间安排。必须结合实际图验证各段时间位置。

新增执行要求：
1. 原始 TTS 非静音不等于对齐结果非静音；对齐 WAV 必须单独检查。
2. 渲染前断言对齐旁白包含有效非静音样本；失败就停止。
3. 最终 MP4 解码后，检查每个旁白段确实存在，而不是只检查总音轨有声音。
4. 同时检查段间重叠、剪切边界和结果词时点；不能用整条相关系数替代口播内容审核。
5. 最终增益依据实际峰值和响度调整，不固定照抄本次增益。本次最终使用总增益 1.7、limiter limit=0.89。

问题在交付前发现并修正，最终用户接受的文件不是错误中间版本。

## 后续工程边界

当前经验已固化为文档和 AGENTS.md 执行检查，尚未实现通用能力检查器、通用 AppKit 标签工具或对齐时间戳回归测试。如要将这些步骤产品化，应单独修改代码并补测试，不把本次实战通过当成自动化功能已经完备。
