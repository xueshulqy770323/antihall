"""解释器 — 将核查结果翻译成人话。

针对每条声明生成：
1. explanation: 哪句话有问题、为什么
2. suggestion: 应该怎么改（给出正确数值）
3. evidence_url: 可点击验证的证据链接
"""
from __future__ import annotations

from antihall.models import (
    ClaimReport,
    Evidence,
    FinancialClaim,
    Verdict,
)
from antihall.extractor.claim_extractor import normalize_to_yi


class Explainer:
    """生成人话解释和修改建议。"""

    def explain(self, report: ClaimReport) -> ClaimReport:
        """为报告填充 explanation 和 suggestion 字段。"""
        claim = report.claim
        evidence = report.evidence

        if report.verdict == Verdict.CORRECT:
            report.explanation = self._explain_correct(claim, evidence)
            report.suggestion = ""

        elif report.verdict == Verdict.HALLUCINATED:
            report.explanation = self._explain_hallucinated(claim, evidence, report.deviation)
            report.suggestion = self._suggest_correction(claim, evidence)

        elif report.verdict == Verdict.UNVERIFIABLE:
            report.explanation = self._explain_unverifiable(claim)
            report.suggestion = ""

        elif report.verdict == Verdict.ERROR:
            report.explanation = "该声明无法解析出可验证的数值。"
            report.suggestion = ""

        return report

    # ------------------------------------------------------------------- #
    # 各判定结果的解释
    # ------------------------------------------------------------------- #

    def _explain_correct(self, claim: FinancialClaim, ev: Evidence) -> str:
        """正确声明的解释。"""
        return (
            f"核查通过。{claim.entity}{claim.year}年{claim.metric}"
            f"为{ev.actual_value}{ev.unit}（数据源：{ev.source_name}），"
            f"文本中写的是{claim.value}{claim.unit}，数值一致。"
        )

    def _explain_hallucinated(
        self,
        claim: FinancialClaim,
        ev: Evidence,
        deviation: float,
    ) -> str:
        """幻觉声明的解释。"""
        # 计算偏差描述
        if claim.metric in ("毛利率", "净利率", "资产负债率", "ROE",
                            "同比增长率", "同比增减率"):
            diff_desc = f"偏差{abs(deviation):.1f}个百分点"
        else:
            diff_desc = f"偏差{abs(deviation):.1%}"

        direction = "高" if deviation > 0 else "低"

        return (
            f"数字幻觉。文本称{claim.entity}{claim.year}年{claim.metric}"
            f"为{claim.value}{claim.unit}，但{ev.source_name}数据显示"
            f"实际值为{ev.actual_value}{ev.unit}，"
            f"文本比真实值{direction}{diff_desc}。"
        )

    def _explain_unverifiable(self, claim: FinancialClaim) -> str:
        """无法验证声明的解释。"""
        reasons = []
        if not claim.entity:
            reasons.append("未识别到公司名")
        if claim.year is None:
            reasons.append("未识别到年份")
        if not reasons:
            reasons.append("数据源中未找到该公司该年份的财报数据")

        return (
            f"无法验证。原因：{'、'.join(reasons)}。"
            f"建议人工核查{claim.entity or '该公司'}"
            f"{claim.year or '对应年份'}的{claim.metric}数据。"
        )

    def _suggest_correction(self, claim: FinancialClaim, ev: Evidence) -> str:
        """修改建议。"""
        return (
            f"建议修改为：{claim.entity}{claim.year}年{claim.metric}"
            f"为{ev.actual_value}{ev.unit}。"
            f"证据来源：{ev.url}"
        )


# ----------------------------------------------------------------------- #
# 全局单例
# ----------------------------------------------------------------------- #
_default_explainer = Explainer()


def explain_report(report: ClaimReport) -> ClaimReport:
    """便捷函数：解释单个报告。"""
    return _default_explainer.explain(report)
