"""Support plan, sponsor benefits, and service entry points."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from web.components.common import has_premium_access, inject_css
from web.components.sidebar import render_sidebar


def _current_version() -> str:
    try:
        return version("tradingagents-astock")
    except PackageNotFoundError:
        return "0.2.7"


st.set_page_config(
    page_title="支持开源计划",
    page_icon="♥",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

with st.sidebar:
    render_sidebar()

st.markdown(
    """
    <div class="ta-page-header">
        <div class="ta-eyebrow">OPEN SOURCE SUPPORT</div>
        <h1 class="ta-page-title">支持开源计划</h1>
        <div class="ta-page-subtitle">
            核心源码继续按 Apache 2.0 开放。赞助用于维护数据接口、发布安装包、完善自动报告和提供持续支持。
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info("所有研究结果仅用于学习和技术演示，不构成证券投资咨询或收益承诺。")

st.subheader("权益方案")
community, supporter, pro, enterprise = st.columns(4, gap="small")

with community.container(border=True):
    st.markdown("#### 社区版")
    st.markdown("**免费**")
    st.write("GitHub 源码、本地运行、自备模型 Key、社区更新和 Issue 支持。")

with supporter.container(border=True):
    st.markdown("#### 支持者版")
    st.markdown("**99 元 / 年**")
    st.write("官方 Windows 一键包、国内镜像通道、稳定更新、配置指南和模板包。")

with pro.container(border=True):
    st.markdown("#### Pro 版")
    st.markdown("**39 元 / 月或 299 元 / 年**")
    st.write("支持者权益、每日投研报告、定时任务、报告模板和优先支持；默认自备模型 Key。")

with enterprise.container(border=True):
    st.markdown("#### 私有部署")
    st.markdown("**2999 元起**")
    st.write("环境部署、模型与数据源接入、定制 Agent、培训和可选长期支持。")

st.caption("早期永久支持权益只能覆盖本地安装包和模板，不包含永久云资源或无限人工支持。")

st.divider()
support_col, value_col = st.columns([1, 1.35], gap="large")

with support_col:
    st.subheader("赞助与联系")
    support_url = os.getenv("TA_SUPPORT_URL", "").strip()
    contact = os.getenv("TA_SUPPORT_CONTACT", "").strip()
    parsed = urlparse(support_url)

    if support_url and parsed.scheme == "https" and parsed.netloc:
        st.link_button("打开官方支持入口", support_url, type="primary", use_container_width=True)
    else:
        st.warning("购买入口尚未配置。请勿向 README 或第三方评论区中的非官方账户付款。")

    if contact:
        st.markdown("**官方联系渠道**")
        st.write(contact)
    else:
        st.caption("维护者可通过环境变量 TA_SUPPORT_CONTACT 配置官方联系方式。")

    sponsor_image = Path(__file__).resolve().parents[2] / "assets" / "wechat-sponsor.jpg"
    sponsor_qr_enabled = os.getenv("TA_SPONSOR_QR_ENABLED", "").strip().lower() == "true"
    if sponsor_qr_enabled and sponsor_image.exists():
        st.image(str(sponsor_image), caption="本地配置的赞助二维码", width=260)
    elif sponsor_image.exists():
        st.caption("本地赞助二维码已禁用；确认收款主体后可设置 TA_SPONSOR_QR_ENABLED=true。")
    else:
        st.caption("赞助二维码未包含在当前构建中。")

with value_col:
    st.subheader("你支持的不是一份代码")
    st.markdown(
        """
        - **省配置：** 官方构建、依赖检查和模型配置指南。
        - **省时间：** 自选股批量任务、每日模板化报告和历史归档。
        - **更稳定：** 数据接口适配、发布校验和稳定更新通道。
        - **可交付：** 私有部署、内部模型接入和定制 Agent 服务。
        - **持续维护：** 问题排查、版本升级和安全修复。
        """
    )
    st.link_button(
        "查看完整商业化说明",
        "https://github.com/simonlin1212/TradingAgents-astock/blob/main/docs/COMMERCIALIZATION.md",
        use_container_width=True,
    )

st.divider()
st.subheader("服务边界")
st.write(
    "支持费用对应软件交付、自动化工具和技术服务，不对应具体证券结论、交易指令或投资收益。"
    "模型调用费、第三方数据费和云资源费如有发生，将在购买前单独说明。"
)

st.subheader("私有部署与定制 Agent")
enterprise_contact = os.getenv("TA_ENTERPRISE_CONTACT", "").strip()
st.write("标准交付包含 Docker 部署、模型接入、管理员配置、自动日报、培训和验收。定制 Agent 按数据、工具和输出契约单独评估。")
if enterprise_contact:
    st.markdown("**企业服务联系渠道**")
    st.write(enterprise_contact)
else:
    st.caption("企业服务渠道尚未配置，可通过 TA_ENTERPRISE_CONTACT 设置。")
private_doc_col, brief_doc_col = st.columns(2)
private_doc_col.link_button(
    "查看私有部署说明",
    "https://github.com/simonlin1212/TradingAgents-astock/blob/main/docs/PRIVATE_DEPLOYMENT.md",
    use_container_width=True,
)
brief_doc_col.link_button(
    "下载定制 Agent 需求模板",
    "https://github.com/simonlin1212/TradingAgents-astock/blob/main/docs/CUSTOM_AGENT_BRIEF.md",
    use_container_width=True,
)

st.divider()
st.subheader("官方构建更新")
st.caption(
    "更新检查优先使用 TA_UPDATE_MANIFEST_URL 配置的国内镜像，失败时回退到 GitHub Releases。"
    "下载包必须通过 SHA-256 校验。"
)
current_version = _current_version()
st.write(f"当前版本：`{current_version}`")

if st.button("检查更新", use_container_width=True):
    from tradingagents.release_update import check_for_update

    try:
        available = check_for_update(current_version)
    except RuntimeError as exc:
        st.warning(str(exc))
    else:
        if available is None:
            st.success("当前已是最新版本。")
        else:
            st.success(f"发现新版本 {available.version}")
            st.code(available.sha256, language=None)
            if has_premium_access("supporter"):
                for index, url in enumerate(available.urls):
                    label = "国内镜像下载" if index == 0 and len(available.urls) > 1 else "GitHub 下载"
                    st.link_button(label, url, use_container_width=True)
            else:
                st.info("官方构建下载属于支持者版权益，请先完成支持或激活。")
