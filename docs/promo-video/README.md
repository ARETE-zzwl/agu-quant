# TradingAgents-Astock 宣传视频素材包

本目录包含基于本地真实 Web UI 制作的宣传文案、分镜、离线中文配音和可直接播放的 MP4。

## 成品

- `output/00-overview.mp4`：产品总览片，约 96 秒。
- `output/01-deep-research.mp4`：多 Agent 深度投研模块，约 38 秒。
- `output/02-quant-research.mp4`：行情、选股、因子与盯盘模块，约 43 秒。
- `output/03-execution-automation.mp4`：模拟盘、基金与日报模块，约 44 秒。
- `output/thumbnail.png`：发布封面。

## 文案与制作文件

- `PROMO_COPY.md`：主标语、长短文案、发布标题与平台配文。
- `STORYBOARD.md`：逐镜头画面、配音与剪辑边界。
- `build_video.py`：使用 Pillow、Windows 离线中文语音和 FFmpeg 重建成片。
- `assets/`：从本地实际页面采集的 1280×720 素材。

## 重建

```powershell
python docs/promo-video/build_video.py
```

脚本不会调用模型 API，也不会修改项目业务数据。需要 Windows 的 `Microsoft Huihui Desktop` 中文语音和可执行的 `ffmpeg` / `ffprobe`。

若要替换为更自然的配音，请将同名 WAV 放入 `audio/` 后执行：

```powershell
python docs/promo-video/build_video.py --skip-tts
```

成片仅用于项目介绍。画面中的行情、评分、回测与报告均不构成证券投资建议或收益承诺。
