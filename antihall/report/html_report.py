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

from antihall.models import CheckResult, ClaimReport, Verdict, FinancialClaim, SemanticClaim, SemanticType


# 颜色方案
_COLORS = {
    Verdict.HALLUCINATED: "#ff4d4f",  # 红色
    Verdict.CORRECT: "#52c41a",       # 绿色
    Verdict.UNVERIFIABLE: "#faad14",  # 橙色
    Verdict.ERROR: "#722ed1",         # 紫色
}

_LABELS = {
    Verdict.HALLUCINATED: "\u5e7b\u89c9",  # 幻觉
    Verdict.CORRECT: "\u6b63\u786e",    # 正确
    Verdict.UNVERIFIABLE: "\u65e0\u6cd5\u9a8c\u8bc1",  # 无法验证
    Verdict.ERROR: "\u9519\u8bef",      # 错误
}

_SEM_TYPE_LABELS = {
    SemanticType.CAUSAL: "\u56e0\u679c\u7f16\u9020",        # 因果编造
    SemanticType.TREND_REVERSAL: "\u8d8b\u52bf\u98a0\u5012",    # 趋势颠倒
    SemanticType.TEMPORAL_MISMATCH: "\u65f6\u95f4\u9519\u4f4d",  # 时间错位
    SemanticType.METRIC_CONFUSION: "\u6307\u6807\u6df7\u6dc6",    # 指标混淆
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
    """Render a single claim's detail card (supports numeric + semantic)."""
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
    label = _LABELS.get(v, "\u672a\u77e5")  # 未知

    parts: list[str] = []
    parts.append(f'<div class="claim-card {card_cls}">')

    # Header: badge + claim type label
    parts.append('<div class="claim-header">')
    parts.append(f'<span class="badge {badge_cls}">{label}</span>')
    # Semantic type badge (extra)
    if isinstance(claim, SemanticClaim):
        sem_label = _SEM_TYPE_LABELS.get(claim.semantic_type, "")
        if sem_label:
            parts.append(
                f'<span class="badge" style="background:#722ed1;">{html.escape(sem_label)}</span>'
            )
    parts.append(f'<span style="color:#888;font-size:14px;">\u7b2c {index} \u6761</span>')
    parts.append("</div>")

    # Original text
    parts.append(
        f'<div class="claim-raw">\"{html.escape(claim.raw_text)}\"</div>'
    )

    # Detail rows — different for numeric vs semantic
    if isinstance(claim, SemanticClaim):
        parts.extend(_render_semantic_details(claim, report, ev))
    else:
        parts.extend(_render_numeric_details(claim, report, ev))

    # Explanation (shared)
    if report.explanation:
        parts.append(f'<div class="detail-row" style="margin-top:12px;">'
                     f'<span class="key">\u89e3\u91ca</span>'
                     f'<span class="val">{html.escape(report.explanation)}</span></div>')

    # Evidence link
    if ev and ev.url:
        parts.append(
            f'<a class="evidence-link" href="{ev.url}" target="_blank">'
            f"\u67e5\u770b\u8bc1\u636e\u6765\u6e90 \u2192</a>"
        )

    # Trend data (for semantic trend claims)
    if ev and ev.trend_data:
        trend_str = " \u2192 ".join(
            f"{d['year']}\uff1a{d['value']}" for d in ev.trend_data
        )
        parts.append(
            f'<div class="detail-row" style="margin-top:8px;">'
            f'<span class="key">\u5386\u5e74\u6570\u636e</span>'
            f'<span class="val">{html.escape(trend_str)}</span></div>'
        )

    # Suggestion
    if report.suggestion:
        parts.append('<div class="suggestion-box">')
        parts.append('<div class="title">\u4fee\u6539\u5efa\u8bae</div>')
        parts.append(html.escape(report.suggestion))
        parts.append("</div>")

    parts.append("</div>")  # claim-card
    return "\n".join(parts)


def _render_numeric_details(claim, report, ev) -> list[str]:
    """Render detail rows for a numeric (FinancialClaim) claim."""
    parts: list[str] = []
    parts.append(f'<div class="detail-row"><span class="key">\u516c\u53f8</span>'
                 f'<span class="val">{html.escape(claim.entity or "\u672a\u8bc6\u522b")}</span></div>')
    parts.append(f'<div class="detail-row"><span class="key">\u6307\u6807</span>'
                 f'<span class="val">{html.escape(claim.metric)}</span></div>')
    parts.append(f'<div class="detail-row"><span class="key">\u58f0\u79f0\u503c</span>'
                 f'<span class="val">{claim.value}{claim.unit}</span></div>')

    if ev and ev.actual_value is not None:
        parts.append(f'<div class="detail-row"><span class="key">\u771f\u5b9e\u503c</span>'
                     f'<span class="val">{ev.actual_value}{ev.unit}</span></div>')

    if report.deviation is not None:
        if claim.metric in ("\u6bdb\u5229\u7387", "\u51c0\u5229\u7387", "\u8d44\u4ea7\u8d1f\u503a\u7387", "ROE",
                            "\u540c\u6bd4\u589e\u957f\u7387", "\u540c\u6bd4\u589e\u51cf\u7387"):
            dev_str = f"{abs(report.deviation):.1f}\u4e2a\u767e\u5206\u70b9"
        else:
            dev_str = f"{abs(report.deviation):.1%}"
        parts.append(f'<div class="detail-row"><span class="key">\u504f\u5dee</span>'
                     f'<span class="val">{dev_str}</span></div>')
    return parts


def _render_semantic_details(claim, report, ev) -> list[str]:
    """Render detail rows for a semantic (SemanticClaim) claim."""
    parts: list[str] = []
    parts.append(f'<div class="detail-row"><span class="key">\u516c\u53f8</span>'
                 f'<span class="val">{html.escape(claim.entity or "\u672a\u8bc6\u522b")}</span></div>')
    parts.append(f'<div class="detail-row"><span class="key">\u58f0\u660e</span>'
                 f'<span class="val">{html.escape(claim.claim_text or claim.raw_text)}</span></div>')

    # Type-specific details
    if claim.semantic_type == SemanticType.CAUSAL:
        if claim.claimed_cause:
            parts.append(f'<div class="detail-row"><span class="key">\u58f0\u79f0\u539f\u56e0</span>'
                         f'<span class="val">{html.escape(claim.claimed_cause)}</span></div>')
        if claim.claimed_effect:
            parts.append(f'<div class="detail-row"><span class="key">\u58f0\u79f0\u7ed3\u679c</span>'
                         f'<span class="val">{html.escape(claim.claimed_effect)}</span></div>')

    elif claim.semantic_type == SemanticType.TREND_REVERSAL:
        if claim.claimed_direction:
            parts.append(f'<div class="detail-row"><span class="key">\u58f0\u79f0\u8d8b\u52bf</span>'
                         f'<span class="val">{html.escape(claim.claimed_direction)}</span></div>')
        if claim.claimed_period:
            parts.append(f'<div class="detail-row"><span class="key">\u58f0\u79f0\u65f6\u671f</span>'
                         f'<span class="val">{html.escape(claim.claimed_period)}</span></div>')

    elif claim.semantic_type == SemanticType.TEMPORAL_MISMATCH:
        if claim.claimed_year:
            parts.append(f'<div class="detail-row"><span class="key">\u58f0\u79f0\u5e74\u4efd</span>'
                         f'<span class="val">{claim.claimed_year}</span></div>')
        if claim.actual_year_data:
            parts.append(f'<div class="detail-row"><span class="key">\u5b9e\u9645\u5e74\u4efd</span>'
                         f'<span class="val">{claim.actual_year_data}</span></div>')

    elif claim.semantic_type == SemanticType.METRIC_CONFUSION:
        if claim.claimed_metric:
            parts.append(f'<div class="detail-row"><span class="key">\u58f0\u79f0\u6307\u6807</span>'
                         f'<span class="val">{html.escape(claim.claimed_metric)}</span></div>')
        if claim.actual_metric:
            parts.append(f'<div class="detail-row"><span class="key">\u5b9e\u9645\u6307\u6807</span>'
                         f'<span class="val">{html.escape(claim.actual_metric)}</span></div>')

    # Evidence value if available
    if ev and ev.actual_value is not None:
        parts.append(f'<div class="detail-row"><span class="key">\u771f\u5b9e\u6570\u636e</span>'
                     f'<span class="val">{ev.actual_value}{ev.unit}</span></div>')

    return parts


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
