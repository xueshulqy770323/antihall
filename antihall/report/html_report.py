"""HTML 可视化报告 — 生成带高亮标注的检测报告 HTML。

功能：
- 原文中有问题的句子红色高亮
- 正确的句子绿色标注
- 每条声明附带：判定结论、真实数据、偏差、证据链接、修改建议
- 顶部显示摘要统计
"""
from __future__ import annotations

import html
from typing import Optional

from antihall.models import CheckResult, ClaimReport, Verdict


# 颜色方案
_COLORS = {
    Verdict.HALLUCINATED: "#ff4d4f",  # 红色
    Verdict.CORRECT: "#52c41a",       # 绿色
    Verdict.UNVERIFIABLE: "#faad14",  # 橙色
    Verdict.ERROR: "#722ed1",         # 紫色
}

_LABELS = {
    Verdict.HALLUCINATED: "幻觉",
    Verdict.CORRECT: "正确",
    Verdict.UNVERIFIABLE: "无法验证",
    Verdict.ERROR: "错误",
}


_CSS = """
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f5f7fa; color: #333; line-height: 1.8; padding: 40px 20px;
}
.container { max-width: 960px; margin: 0 auto; }
.header {
    background: #fff; border-radius: 12px; padding: 32px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 24px;
}
.header h1 { font-size: 24px; margin-bottom: 16px; }
.summary-bar { display: flex; gap: 16px; flex-wrap: wrap; }
.stat-card {
    flex: 1; min-width: 140px; padding: 16px; border-radius: 8px;
    text-align: center;
}
.stat-card .num { font-size: 32px; font-weight: 700; }
.stat-card .label { font-size: 14px; color: #888; margin-top: 4px; }
.stat-hallucinated { background: #fff1f0; }
.stat-hallucinated .num { color: #ff4d4f; }
.stat-correct { background: #f6ffed; }
.stat-correct .num { color: #52c41a; }
.stat-unverifiable { background: #fffbe6; }
.stat-unverifiable .num { color: #faad14; }
.stat-rate { background: #f0f5ff; }
.stat-rate .num { color: #1890ff; }
.risk-badge {
    display: inline-block; padding: 4px 12px; border-radius: 4px;
    font-weight: 600; margin-left: 8px;
}
.risk-高风险 { background: #ff4d4f; color: #fff; }
.risk-中风险 { background: #faad14; color: #fff; }
.risk-低风险 { background: #1890ff; color: #fff; }
.risk-无风险 { background: #52c41a; color: #fff; }
.section {
    background: #fff; border-radius: 12px; padding: 32px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 24px;
}
.section h2 { font-size: 18px; margin-bottom: 16px; padding-bottom: 12px;
    border-bottom: 1px solid #eee; }
.original-text {
    padding: 20px; background: #fafafa; border-radius: 8px;
    font-size: 15px; line-height: 2;
}
.highlight-hallucinated {
    background: #fff1f0; border-bottom: 2px solid #ff4d4f; padding: 2px 4px;
    border-radius: 2px;
}
.highlight-correct {
    background: #f6ffed; border-bottom: 2px solid #52c41a; padding: 2px 4px;
    border-radius: 2px;
}
.highlight-unverifiable {
    background: #fffbe6; border-bottom: 2px solid #faad14; padding: 2px 4px;
    border-radius: 2px;
}
.claim-card {
    border: 1px solid #eee; border-radius: 8px; padding: 20px;
    margin-bottom: 16px;
}
.claim-card.hallucinated { border-left: 4px solid #ff4d4f; }
.claim-card.correct { border-left: 4px solid #52c41a; }
.claim-card.unverifiable { border-left: 4px solid #faad14; }
.claim-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.badge {
    padding: 2px 8px; border-radius: 4px; font-size: 12px;
    font-weight: 600; color: #fff;
}
.badge-hallucinated { background: #ff4d4f; }
.badge-correct { background: #52c41a; }
.badge-unverifiable { background: #faad14; }
.claim-raw {
    background: #f5f5f5; padding: 12px; border-radius: 6px;
    margin-bottom: 12px; font-size: 14px;
}
.detail-row { margin-bottom: 8px; }
.detail-row .key { color: #888; display: inline-block; width: 100px; }
.detail-row .val { font-weight: 500; }
.evidence-link {
    display: inline-block; margin-top: 8px; color: #1890ff;
    text-decoration: none; border-bottom: 1px dashed #1890ff;
}
.suggestion-box {
    background: #e6f7ff; border: 1px solid #91d5ff; border-radius: 6px;
    padding: 12px 16px; margin-top: 12px;
}
.suggestion-box .title { font-weight: 600; color: #096dd9; margin-bottom: 4px; }
.footer {
    text-align: center; padding: 24px; color: #999; font-size: 13px;
}
</style>
"""


def generate_html_report(result: CheckResult, title: str = "金融报告幻觉检测报告") -> str:
    """生成完整的 HTML 报告。

    Args:
        result: 核查结果
        title: 报告标题

    Returns:
        完整的 HTML 字符串
    """
    parts: list[str] = []
    parts.append(f"<!DOCTYPE html>")
    parts.append(f'<html lang="zh-CN"><head><meta charset="UTF-8">')
    parts.append(f"<title>{html.escape(title)}</title>")
    parts.append(_CSS)
    parts.append("</head><body>")
    parts.append('<div class="container">')

    # ── 头部摘要 ──
    parts.append('<div class="header">')
    parts.append(f"<h1>{html.escape(title)}</h1>")
    parts.append(
        f'<p style="color:#888;margin-bottom:16px;">'
        f'风险等级：<span class="risk-badge risk-{result.risk_level}">'
        f'{result.risk_level}</span></p>'
    )
    parts.append('<div class="summary-bar">')
    parts.append(
        f'<div class="stat-card stat-hallucinated">'
        f'<div class="num">{result.hallucinated_count}</div>'
        f'<div class="label">幻觉</div></div>'
    )
    parts.append(
        f'<div class="stat-card stat-correct">'
        f'<div class="num">{result.correct_count}</div>'
        f'<div class="label">正确</div></div>'
    )
    parts.append(
        f'<div class="stat-card stat-unverifiable">'
        f'<div class="num">{result.unverifiable_count}</div>'
        f'<div class="label">无法验证</div></div>'
    )
    parts.append(
        f'<div class="stat-card stat-rate">'
        f'<div class="num">{result.hallucination_rate:.0%}</div>'
        f'<div class="label">幻觉率</div></div>'
    )
    parts.append("</div>")  # summary-bar
    parts.append(f'<p style="margin-top:16px;color:#666;">{html.escape(result.summary())}</p>')
    parts.append("</div>")  # header

    # ── 原文高亮 ──
    parts.append('<div class="section">')
    parts.append("<h2>原文标注</h2>")
    parts.append('<div class="original-text">')
    highlighted = _highlight_text(result)
    parts.append(highlighted)
    parts.append("</div></div>")  # original-text / section

    # ── 逐条声明详情 ──
    parts.append('<div class="section">')
    parts.append("<h2>逐条核查详情</h2>")
    for i, report in enumerate(result.claims, 1):
        parts.append(_render_claim_card(i, report))
    parts.append("</div>")  # section

    # ── 页脚 ──
    parts.append('<div class="footer">')
    parts.append(
        "由 antihall 生成 · 数据源：AKShare（A 股公开财报）"
        " · 本工具仅提供数据核查参考，不构成投资建议"
    )
    parts.append("</div>")

    parts.append("</div></body></html>")
    return "\n".join(parts)


def _highlight_text(result: CheckResult) -> str:
    """对原文中有问题的句子做高亮。"""
    text = result.input_text

    # 按 claim 的 raw_text 来定位
    for report in result.claims:
        raw = report.claim.raw_text
        if not raw:
            continue
        verdict = report.verdict
        if verdict == Verdict.HALLUCINATED:
            cls = "highlight-hallucinated"
        elif verdict == Verdict.CORRECT:
            cls = "highlight-correct"
        else:
            cls = "highlight-unverifiable"
        escaped = html.escape(raw)
        replacement = f'<span class="{cls}">{escaped}</span>'
        text = text.replace(raw, replacement, 1)

    # 没有 span 包裹的文本也要转义
    # 简单处理：已经转义过的就不动了
    return text


def _render_claim_card(index: int, report: ClaimReport) -> str:
    """渲染单条声明的详情卡片。"""
    claim = report.claim
    ev = report.evidence
    v = report.verdict

    cls_map = {
        Verdict.HALLUCINATED: "hallucinated",
        Verdict.CORRECT: "correct",
        Verdict.UNVERIFIABLE: "unverifiable",
        Verdict.ERROR: "unverifiable",
    }
    badge_cls_map = {
        Verdict.HALLUCINATED: "badge-hallucinated",
        Verdict.CORRECT: "badge-correct",
        Verdict.UNVERIFIABLE: "badge-unverifiable",
        Verdict.ERROR: "badge-unverifiable",
    }

    card_cls = cls_map.get(v, "unverifiable")
    badge_cls = badge_cls_map.get(v, "badge-unverifiable")
    label = _LABELS.get(v, "未知")

    parts: list[str] = []
    parts.append(f'<div class="claim-card {card_cls}">')

    # 头部
    parts.append('<div class="claim-header">')
    parts.append(f'<span class="badge {badge_cls}">{label}</span>')
    parts.append(f'<span style="color:#888;font-size:14px;">第 {index} 条</span>')
    parts.append("</div>")

    # 原文
    parts.append(
        f'<div class="claim-raw">"{html.escape(claim.raw_text)}"</div>'
    )

    # 详情
    parts.append(f'<div class="detail-row"><span class="key">公司</span>'
                 f'<span class="val">{html.escape(claim.entity or "未识别")}</span></div>')
    parts.append(f'<div class="detail-row"><span class="key">指标</span>'
                 f'<span class="val">{html.escape(claim.metric)}</span></div>')
    parts.append(f'<div class="detail-row"><span class="key">声称值</span>'
                 f'<span class="val">{claim.value}{claim.unit}</span></div>')

    if ev and ev.actual_value is not None:
        parts.append(f'<div class="detail-row"><span class="key">真实值</span>'
                     f'<span class="val">{ev.actual_value}{ev.unit}</span></div>')

    if report.deviation is not None:
        if claim.metric in ("毛利率", "净利率", "资产负债率", "ROE",
                            "同比增长率", "同比增减率"):
            dev_str = f"{abs(report.deviation):.1f}个百分点"
        else:
            dev_str = f"{abs(report.deviation):.1%}"
        parts.append(f'<div class="detail-row"><span class="key">偏差</span>'
                     f'<span class="val">{dev_str}</span></div>')

    if report.explanation:
        parts.append(f'<div class="detail-row" style="margin-top:12px;">'
                     f'<span class="key">解释</span>'
                     f'<span class="val">{html.escape(report.explanation)}</span></div>')

    # 证据链接
    if ev and ev.url:
        parts.append(
            f'<a class="evidence-link" href="{ev.url}" target="_blank">'
            f"查看证据来源 →</a>"
        )

    # 修改建议
    if report.suggestion:
        parts.append('<div class="suggestion-box">')
        parts.append('<div class="title">修改建议</div>')
        parts.append(html.escape(report.suggestion))
        parts.append("</div>")

    parts.append("</div>")  # claim-card
    return "\n".join(parts)


def save_html_report(result: CheckResult, filepath: str, title: str = "") -> str:
    """生成 HTML 报告并保存到文件。

    Args:
        result: 核查结果
        filepath: 保存路径
        title: 报告标题

    Returns:
        保存的文件路径
    """
    html_content = generate_html_report(result, title or "金融报告幻觉检测报告")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    return filepath
