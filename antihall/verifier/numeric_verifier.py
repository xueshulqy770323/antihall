"""数字核查引擎 — 对比声称值与真实值，判定是否幻觉。

核查逻辑：
1. 将声称值和真实值统一到同一单位
2. 计算偏差百分比
3. 根据指标类型设定容差阈值
4. 超出阈值 → 幻觉；在阈值内 → 正确
"""
from __future__ import annotations

import logging
from typing import Optional

from antihall.models import (
    ClaimReport,
    Evidence,
    FinancialClaim,
    Verdict,
)
from antihall.extractor.claim_extractor import normalize_to_yi

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# 容差设定：不同指标允许的偏差百分比
# --------------------------------------------------------------------------- #
# 绝对值指标（营收、利润）容差 2%：因为四舍五入和小数位差异
# 比率指标（毛利率）容差 1 个百分点
# 增长率指标容差 5%：因为计算基数不同
TOLERANCE: dict[str, float] = {
    "营收": 0.02,         # 2%
    "净利润": 0.02,
    "归母净利润": 0.02,
    "扣非净利润": 0.02,
    "毛利率": 1.0,        # 1个百分点（绝对值比较）
    "净利率": 1.0,
    "资产负债率": 1.0,
    "ROE": 1.0,
    "同比增长率": 5.0,    # 5个百分点
    "同比增减率": 5.0,
}

# 比率类指标：用百分点而不是百分比偏差
RATIO_METRICS = {"毛利率", "净利率", "资产负债率", "ROE", "同比增长率", "同比增减率"}


class NumericVerifier:
    """数字核查引擎。"""

    def verify(
        self,
        claim: FinancialClaim,
        evidence: Optional[Evidence],
    ) -> ClaimReport:
        """核查单条声明。

        Args:
            claim: 提取的金融声明
            evidence: 数据源返回的真实证据（可能为 None）

        Returns:
            ClaimReport 包含 verdict + deviation
        """
        report = ClaimReport(claim=claim, evidence=evidence)

        if evidence is None:
            report.verdict = Verdict.UNVERIFIABLE
            report.deviation = None
            return report

        if evidence.actual_value is None:
            report.verdict = Verdict.UNVERIFIABLE
            return report

        if claim.value is None:
            report.verdict = Verdict.ERROR
            return report

        # 统一单位后比较
        claimed_normalized = normalize_to_yi(claim.value, claim.unit)
        actual_normalized = normalize_to_yi(
            evidence.actual_value, evidence.unit
        )

        metric = claim.metric
        tolerance = TOLERANCE.get(metric, 0.02)

        if metric in RATIO_METRICS:
            # 比率指标：直接比较百分点
            diff = abs(claimed_normalized - actual_normalized)
            report.deviation = diff if diff != 0 else 0.0
        else:
            # 绝对值指标：相对偏差
            if actual_normalized == 0:
                report.verdict = Verdict.UNVERIFIABLE
                return report
            report.deviation = (
                claimed_normalized - actual_normalized
            ) / abs(actual_normalized)

        # 判定
        if metric in RATIO_METRICS:
            is_hallucinated = abs(report.deviation) > tolerance
        else:
            is_hallucinated = abs(report.deviation) > tolerance

        if is_hallucinated:
            report.verdict = Verdict.HALLUCINATED
        else:
            report.verdict = Verdict.CORRECT

        return report
