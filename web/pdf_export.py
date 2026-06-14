"""Generate PDF reports from analysis results using fpdf2."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF


_FONT_CANDIDATES = [
    # Windows TTF first (TrueType, not collection — better fpdf2 support)
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simkai.ttf",
    "C:/Windows/Fonts/simfang.ttf",
    "C:/Windows/Fonts/simsunb.ttf",
    # Windows TTC fallback
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    # Mac
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    # Linux
    "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf",
    "/usr/share/fonts/noto-cjk/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _find_cjk_font() -> str | None:
    for path in _FONT_CANDIDATES:
        p = Path(path)
        if p.exists():
            return str(p)
    return None


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def _strip_md_inline(text: str) -> str:
    """Remove inline markdown formatting: **bold**, *italic*, `code`, [link](url)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text


def _signal_color(signal: str) -> tuple[int, int, int]:
    s = signal.upper()
    if "BUY" in s:
        return (34, 197, 94)
    if "SELL" in s:
        return (239, 68, 68)
    return (251, 191, 36)


_REPORT_SECTIONS = [
    ("market_report", "技术分析报告"),
    ("sentiment_report", "市场情绪报告"),
    ("news_report", "新闻舆情报告"),
    ("fundamentals_report", "基本面报告"),
    ("policy_report", "政策分析报告"),
    ("hot_money_report", "游资追踪报告"),
    ("lockup_report", "解禁/减持报告"),
]


class _ReportPDF(FPDF):
    def __init__(self, ticker: str, trade_date: str, signal: str) -> None:
        super().__init__()
        self.ticker = ticker
        self.trade_date = trade_date
        self.signal = signal
        self._has_cjk = False

        font_path = _find_cjk_font()
        if font_path:
            self.add_font("CJK", "", font_path, uni=True)
            self.add_font("CJK", "B", font_path, uni=True)  # SimHei is already bold
            self._has_cjk = True

    def _use_font(self, style: str = "", size: int = 10) -> None:
        if self._has_cjk:
            self.set_font("CJK", style, size)
        else:
            self.set_font("Helvetica", style, size)

    def header(self) -> None:
        self._use_font("", 8)
        self.set_text_color(150, 150, 150)
        self._safe_cell(0, 6, f"A股多Agent投研分析  |  {self.ticker}  |  {self.trade_date}", align="C")
        self.ln(8)
        self.set_draw_color(60, 60, 60)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self._use_font("", 8)
        self.set_text_color(120, 120, 120)
        self._safe_cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")
        self.ln(4)
        self._use_font("", 6)
        self.set_text_color(160, 160, 160)
        self._safe_cell(0, 4, "仅供学习研究，不构成投资建议", align="C")

    def add_cover(self) -> None:
        self.add_page()
        self.ln(60)

        self._use_font("B", 24)
        self.set_text_color(255, 90, 31)
        self.cell(0, 12, "A股多Agent投研分析报告", align="C")
        self.ln(20)

        self._use_font("B", 36)
        self.set_text_color(30, 30, 30)
        self.cell(0, 18, self.ticker, align="C")
        self.ln(16)

        self._use_font("", 14)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"分析日期: {self.trade_date}", align="C")
        self.ln(8)
        self.cell(0, 10, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C")
        self.ln(20)

        r, g, b = _signal_color(self.signal)
        self._use_font("B", 40)
        self.set_text_color(r, g, b)
        self.cell(0, 20, self.signal.upper(), align="C")
        self.ln(20)

        self._use_font("", 9)
        self.set_text_color(120, 120, 120)
        self.multi_cell(
            0, 5,
            "免责声明: 本报告由 AI 多 Agent 系统自动生成, 仅供学习研究与技术演示, "
            "不构成任何投资建议。投资决策请咨询持牌专业机构。"
            "使用本报告所产生的任何损失由使用者自行承担。",
            align="C",
        )

    def add_section(self, title: str, content: str) -> None:
        self.add_page()
        self._use_font("B", 16)
        self.set_text_color(255, 90, 31)
        self.cell(0, 10, title)
        self.ln(12)

        cleaned = _strip_think(content)
        self._render_markdown(cleaned)

    @property
    def _text_width(self) -> float:
        """Usable text width accounting for margins."""
        return self.w - self.l_margin - self.r_margin

    def _safe_multi_cell(self, h: float, text: str):
        """multi_cell with explicit width to avoid CJK font issues."""
        try:
            self.multi_cell(self._text_width, h, text)
        except Exception:
            # Fallback: use ASCII-only or skip
            safe = text.encode("ascii", errors="replace").decode("ascii")
            self.multi_cell(self._text_width, h, safe)

    def _safe_cell(self, w: float, h: float, text: str, **kwargs):
        """cell with explicit width."""
        try:
            self.cell(w or self._text_width, h, text, **kwargs)
        except Exception:
            safe = text.encode("ascii", errors="replace").decode("ascii")
            self.cell(w or self._text_width, h, safe, **kwargs)

    def _render_markdown(self, text: str) -> None:
        """Render markdown-formatted text with basic styling."""
        lines = text.split("\n")
        w = self._text_width
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Empty line → small vertical gap
            if not stripped:
                self.ln(3)
                i += 1
                continue

            # Headings: ### → 11pt, ## → 13pt, # → 14pt
            if stripped.startswith("###"):
                self._use_font("B", 11)
                self.set_text_color(50, 50, 50)
                self.cell(0, 7, stripped.lstrip("#").strip())
                self.ln(8)
                i += 1
                continue
            if stripped.startswith("##"):
                self._use_font("B", 13)
                self.set_text_color(40, 40, 40)
                self.cell(0, 8, stripped.lstrip("#").strip())
                self.ln(9)
                i += 1
                continue
            if stripped.startswith("#"):
                self._use_font("B", 14)
                self.set_text_color(255, 90, 31)
                self.cell(0, 9, stripped.lstrip("#").strip())
                self.ln(10)
                i += 1
                continue

            # Horizontal rule
            if stripped in ("---", "***", "___"):
                self.set_draw_color(180, 180, 180)
                y = self.get_y() + 2
                self.line(10, y, self.w - 10, y)
                self.ln(6)
                i += 1
                continue

            # Bullet points (-, *, numbered)
            if re.match(r"^[-*]\s", stripped) or re.match(r"^\d+[.)]\s", stripped):
                self._use_font("", 10)
                self.set_text_color(40, 40, 40)
                if re.match(r"^[-*]\s", stripped):
                    bullet = "  •  "
                    body = stripped[2:].strip()
                else:
                    m = re.match(r"^(\d+[.)])\s*(.*)", stripped)
                    bullet = f"  {m.group(1)} "
                    body = m.group(2)
                body = _strip_md_inline(body)
                self.multi_cell(0, 5.5, bullet + body)
                i += 1
                continue

            # Table rows (|col|col|) → render as plain text with spacing
            if stripped.startswith("|") and stripped.endswith("|"):
                # Skip separator rows like |---|---|
                if re.match(r"^\|[-:\s|]+\|$", stripped):
                    i += 1
                    continue
                self._use_font("", 9)
                self.set_text_color(60, 60, 60)
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                row_text = "    ".join(_strip_md_inline(c) for c in cells)
                self.multi_cell(0, 5, row_text)
                i += 1
                continue

            # Regular paragraph — collect consecutive non-special lines
            para_lines = []
            while i < len(lines):
                ln = lines[i].strip()
                if not ln or ln.startswith("#") or ln.startswith("|") or re.match(r"^[-*]\s", ln) or re.match(r"^\d+[.)]\s", ln) or ln in ("---", "***", "___"):
                    break
                para_lines.append(ln)
                i += 1

            if para_lines:
                self._use_font("", 10)
                self.set_text_color(40, 40, 40)
                para = " ".join(para_lines)
                para = _strip_md_inline(para)
                self.multi_cell(0, 5.5, para)
                self.ln(2)
                continue

            i += 1


def generate_pdf(final_state: dict[str, Any], ticker: str, trade_date: str, signal: str) -> bytes:
    """Generate a PDF report and return it as bytes. Falls back to simple PDF on CJK error."""
    try:
        return _generate_pdf_inner(final_state, ticker, trade_date, signal)
    except Exception:
        return _generate_simple_pdf(ticker, trade_date, signal)


def _generate_pdf_inner(final_state, ticker, trade_date, signal):
    pdf = _ReportPDF(ticker, trade_date, signal)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    pdf.add_cover()

    for key, title in _REPORT_SECTIONS:
        content = final_state.get(key, "")
        if content:
            pdf.add_section(title, str(content))

    debate = final_state.get("investment_debate_state")
    if debate and isinstance(debate, dict):
        parts = []
        if debate.get("bull_history"):
            parts.append(f"=== 多方论点 ===\n{debate['bull_history']}")
        if debate.get("bear_history"):
            parts.append(f"\n=== 空方论点 ===\n{debate['bear_history']}")
        if debate.get("judge_decision"):
            parts.append(f"\n=== 研究经理决策 ===\n{debate['judge_decision']}")
        if parts:
            pdf.add_section("多空辩论", "\n".join(parts))

    trader_decision = final_state.get("trader_investment_decision", "")
    if trader_decision:
        pdf.add_section("交易员决策", _strip_think(str(trader_decision)))

    inv_plan = final_state.get("investment_plan", "")
    if inv_plan:
        pdf.add_section("最终投资建议", _strip_think(str(inv_plan)))

    risk = final_state.get("risk_debate_state")
    if risk and isinstance(risk, dict):
        parts = []
        for key_name, label in [("aggressive_history", "激进观点"),
                                 ("conservative_history", "保守观点"),
                                 ("neutral_history", "中性观点")]:
            if risk.get(key_name):
                parts.append(f"=== {label} ===\n{risk[key_name]}")
        if risk.get("judge_decision"):
            parts.append(f"\n=== 风控决策 ===\n{risk['judge_decision']}")
        if parts:
            pdf.add_section("风控评估", "\n".join(parts))

    final_decision = final_state.get("final_trade_decision", "")
    if final_decision:
        pdf.add_section("最终决策", _strip_think(str(final_decision)))

    return bytes(pdf.output())


def _generate_simple_pdf(ticker: str, trade_date: str, signal: str) -> bytes:
    """Minimal ASCII-safe PDF report as fallback when CJK font fails."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Trading Report: {ticker}", align="C")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Date: {trade_date}  |  Signal: {signal}", align="C")
    pdf.ln(12)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5,
                   "This is a simplified report due to font rendering limitations.\n"
                   "Please view the full report in the web interface.\n\n"
                   "Disclaimer: Generated by AI for research purposes only.\n"
                   "This does NOT constitute investment advice.")
    return bytes(pdf.output())
