"""Build narrated TradingAgents-Astock promo videos from real UI captures."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
AUDIO = ROOT / "audio"
WORK = ROOT / "work"
OUTPUT = ROOT / "output"
SIZE = (1280, 720)


PROJECTS = {
    "00-overview": [
        ("title", "产品总览", "研究 A 股，难的不是没有信息，而是把行情、政策、资金、风险和执行，放进同一套判断链路。"),
        ("01-market-dashboard.png", "市场环境", "TradingAgents Astock 面向 A 股，把实时行情、板块轮动和多条件选股，直接带进本地 Web 工作台。"),
        ("04-stock-screener.png", "多条件选股", "从市场、估值、质量、市值、换手率和涨跌幅出发，快速缩小真正值得研究的范围。"),
        ("02-deep-analysis.png", "七位分析师", "输入六位代码或中文股票名，市场、情绪、新闻、基本面、政策、游资和解禁，七位分析师分别展开研究。"),
        ("11-analysis-report.png", "辩论与报告", "多头与空头交叉辩论，研究经理形成裁决，再由风险角色复核，最终生成结构化报告与 PDF。"),
        ("05-factor-engine.png", "量化验证", "二百九十三个因子、十大分类、回测与策略调权，让主观观点进入可检验的数据框架。"),
        ("10-stock-monitor.png", "持续监控", "从 AI 候选到多周期监控，再到遵守 T 加一规则的模拟盘，研究结果可以继续进入执行和复盘。"),
        ("07-fund-center.png", "跨品种研究", "基金筛选、组合管理和每日投研报告，进一步覆盖跨品种研究与定时自动化。"),
        ("end", "开源 · 本地 · 可追溯", "核心源码开源，支持本地部署和自备模型密钥。TradingAgents Astock，让每个结论都有过程，让每次决策都有边界。仅供学习研究，不构成投资建议。"),
    ],
    "01-deep-research": [
        ("title", "多 Agent 深度投研", "不是让一个模型直接猜答案，而是让不同角色先各自把证据说清楚。"),
        ("02-deep-analysis.png", "七位分析师协作", "七位分析师覆盖技术、情绪、新闻、基本面、政策、游资和解禁，并支持中文股票名称自动解析。"),
        ("11-analysis-report.png", "辩论、裁决、风险复核", "多空辩论之后，由研究经理裁决，再经过风险复核，形成包含论据、评级、行动边界和风险提示的完整报告。"),
        ("end", "让结论可追溯", "让结论可追溯，让分歧可检查。TradingAgents Astock 多 Agent 深度投研。"),
    ],
    "02-quant-research": [
        ("01-market-dashboard.png", "大盘环境", "从大盘状态、涨跌家数与资金信号开始，先确定市场所处的环境。"),
        ("03-sector-board.png", "板块轮动", "行业、概念和涨跌热力图，把板块轮动变成可阅读的排名。"),
        ("04-stock-screener.png", "多条件筛选", "通过市场、估值、质量、市值、换手率和涨跌幅条件，快速缩小研究范围。"),
        ("05-factor-engine.png", "293 个因子", "二百九十三个因子覆盖价值、动量、质量、资金、波动、情绪、技术与复合联动，并提供回测和策略调权。"),
        ("10-stock-monitor.png", "多周期盯盘", "最后用多周期 K 线、因子趋势和策略信号持续监控，而不是只看一次性结果。"),
    ],
    "03-execution-automation": [
        ("09-ai-picks.png", "研究候选", "预设策略或自定义权重先产生研究候选，并明确结果只用于研究和模拟盘。"),
        ("06-paper-trade.png", "A 股模拟盘", "模拟盘遵守 A 股交易时段、T 加一和持仓规则，资产、委托与信号可以延续保存。"),
        ("07-fund-center.png", "基金研究", "基金中心将场外基金、ETF、组合权重和独立模拟舱放进统一界面。"),
        ("08-daily-reports.png", "每日自动报告", "自选股可以按简报、完整或风险模板生成 Markdown 报告，并交给 Windows 任务计划定时执行。"),
        ("end", "研究工作流闭环", "从候选、监控到模拟和日报，让研究工作流真正闭环。仅供学习研究，不构成投资建议。"),
    ],
}


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def title_card(path: Path, title: str, label: str) -> None:
    image = Image.new("RGB", SIZE, "#090d10")
    draw = ImageDraw.Draw(image)
    for x in range(0, SIZE[0], 48):
        draw.line((x, 0, x, SIZE[1]), fill="#11181d", width=1)
    for y in range(0, SIZE[1], 48):
        draw.line((0, y, SIZE[0], y), fill="#11181d", width=1)
    draw.rounded_rectangle((78, 88, 1202, 632), 28, fill="#10171b", outline="#25343a", width=2)
    draw.rectangle((78, 88, 92, 632), fill="#ff7317")
    draw.text((130, 145), "TRADINGAGENTS · ASTOCK", font=font(24, bold=True), fill="#4de0c1")
    draw.text((130, 230), title, font=font(62, bold=True), fill="#f7f2e9")
    draw.text((132, 330), label, font=font(30), fill="#a9b2b7")
    draw.line((132, 430, 820, 430), fill="#ff7317", width=4)
    draw.text((132, 480), "7 AGENTS  ·  293 FACTORS  ·  LOCAL WEB UI", font=font(21), fill="#718087")
    draw.text((132, 560), "仅供学习研究，不构成投资建议", font=font(20), fill="#68747a")
    image.save(path)


def speech(text: str, text_path: Path, wave_path: Path) -> None:
    text_path.write_text(text, encoding="utf-8")
    escaped_text = str(text_path.resolve()).replace("'", "''")
    escaped_wave = str(wave_path.resolve()).replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop'; $env:WINDIR='C:\\Windows'; "
        "Add-Type -AssemblyName System.Speech; "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.SelectVoice('Microsoft Huihui Desktop'); $s.Rate=1; $s.Volume=100; "
        f"$s.SetOutputToWaveFile('{escaped_wave}'); "
        f"$t=[IO.File]::ReadAllText('{escaped_text}',[Text.Encoding]::UTF8); "
        "$s.Speak($t); $s.Dispose()"
    )
    run(["powershell", "-NoProfile", "-Command", command])


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        check=True,
        text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def srt_time(value: float) -> str:
    millis = round(value * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def wrap_caption(text: str, width: int = 24) -> str:
    return "\n".join(text[index : index + width] for index in range(0, len(text), width))


def render_scene(image: Path, wave: Path, caption: str, clip: Path) -> None:
    audio_length = duration(wave)
    total = audio_length + 0.45
    subtitle = clip.with_suffix(".srt")
    subtitle.write_text(
        f"1\n00:00:00,150 --> {srt_time(audio_length + 0.2)}\n{wrap_caption(caption)}\n",
        encoding="utf-8-sig",
    )
    subtitle_rel = subtitle.relative_to(ROOT).as_posix()
    fade_out = max(total - 0.35, 0.2)
    video_filter = (
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x090d10,"
        f"fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out:.3f}:d=0.35,"
        f"subtitles=filename='{subtitle_rel}':force_style='FontName=Microsoft YaHei,"
        "FontSize=21,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=3,BackColour=&H88000000,Outline=1,Shadow=0,MarginV=24,Alignment=2'"
    )
    run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30",
            "-i", str(image.relative_to(ROOT)), "-i", str(wave.relative_to(ROOT)),
            "-vf", video_filter, "-t", f"{total:.3f}",
            "-af", "apad=pad_dur=0.45,loudnorm=I=-16:TP=-1.5:LRA=7",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(clip.relative_to(ROOT)),
        ]
    )


def build_project(name: str, scenes: list[tuple[str, str, str]], skip_tts: bool) -> None:
    clips: list[Path] = []
    for index, (asset, heading, narration) in enumerate(scenes):
        stem = f"{name}-{index:02}"
        if asset in {"title", "end"}:
            image = WORK / f"{stem}.png"
            label = "A 股多智能体投研工作台" if asset == "title" else "OPEN SOURCE · LOCAL FIRST"
            title_card(image, heading, label)
        else:
            image = ASSETS / asset
        if not image.exists():
            raise FileNotFoundError(image)
        wave = AUDIO / f"{stem}.wav"
        if not skip_tts or not wave.exists():
            speech(narration, WORK / f"{stem}.txt", wave)
        clip = WORK / f"{stem}.mp4"
        render_scene(image, wave, narration, clip)
        clips.append(clip)

    concat = WORK / f"{name}-concat.txt"
    concat.write_text(
        "\n".join(f"file '{clip.resolve().as_posix()}'" for clip in clips) + "\n",
        encoding="utf-8",
    )
    run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(concat.relative_to(ROOT)), "-c", "copy", "-movflags", "+faststart",
            str((OUTPUT / f"{name}.mp4").relative_to(ROOT)),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tts", action="store_true", help="Reuse existing WAV files")
    parser.add_argument("--only", choices=PROJECTS, help="Build one video")
    args = parser.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg and ffprobe are required")
    for folder in (ASSETS, AUDIO, WORK, OUTPUT):
        folder.mkdir(parents=True, exist_ok=True)

    selected = {args.only: PROJECTS[args.only]} if args.only else PROJECTS
    for name, scenes in selected.items():
        print(f"Building {name}...")
        build_project(name, scenes, args.skip_tts)

    thumbnail = OUTPUT / "thumbnail.png"
    title_card(thumbnail, "把 A 股研究，变成可追溯的协作", "TradingAgents-Astock 宣传片")
    print(f"Done: {OUTPUT}")


if __name__ == "__main__":
    main()
