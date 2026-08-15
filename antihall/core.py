"""HallucinationChecker — antihall 主接口。

用户只需三行代码完成金融幻觉检测：

    from antihall import HallucinationChecker

    checker = HallucinationChecker()
    result = checker.check("贵州茅台2023年营收1505.6亿元，净利润862.3亿元。")
    print(result.summary())
"""
from __future__ import annotations

import logging
from typing import Optional

from antihall.models import CheckResult, ClaimReport, FinancialClaim
from antihall.extractor.claim_extractor import ClaimExtractor
from antihall.datasource.akshare_source import AKShareDataSource
from antihall.verifier.numeric_verifier import NumericVerifier
from antihall.explainer.explainer import Explainer

logger = logging.getLogger(__name__)


class HallucinationChecker:
    """金融报告幻觉检测器 — 主接口。

    工作流程：
        原文 → [提取声明] → [查真实数据] → [数字核查] → [生成解释] → CheckResult

    Attributes:
        extractor: 声明提取器
        datasource: 数据源（默认 AKShare）
        verifier: 数字核查引擎
        explainer: 解释器
    """

    def __init__(
        self,
        datasource: Optional[AKShareDataSource] = None,
    ):
        self.extractor = ClaimExtractor()
        self.datasource = datasource or AKShareDataSource()
        self.verifier = NumericVerifier()
        self.explainer = Explainer()

    def check(self, text: str) -> CheckResult:
        """检测一段中文金融文本中的幻觉。

        Args:
            text: 待检测文本，如 LLM 生成的财报分析、投研报告等。

        Returns:
            CheckResult 对象，包含每条声明的核查详情。

        Examples:
            >>> checker = HallucinationChecker()
            >>> result = checker.check(
            ...     "贵州茅台2023年营收1505.6亿元，净利润862.3亿元。"
            ... )
            >>> print(result.summary())
            '共检测 2 条声明，其中 0 条幻觉、2 条正确...'
        """
        result = CheckResult(input_text=text)

        # Step 1: 提取声明
        claims = self.extractor.extract(text)
        logger.info(f"提取到 {len(claims)} 条声明")

        # Step 2~4: 逐条 查数据→核查→解释
        for claim in claims:
            # 查真实数据
            evidence = None
            if claim.entity and claim.metric:
                evidence = self.datasource.get_evidence(
                    entity=claim.entity,
                    metric=claim.metric,
                    year=claim.year,
                )

            # 数字核查
            report = self.verifier.verify(claim, evidence)

            # 生成解释
            report = self.explainer.explain(report)

            result.claims.append(report)

        return result

    def check_and_report(
        self,
        text: str,
        output_path: str,
        title: str = "",
    ) -> CheckResult:
        """检测并生成 HTML 报告。

        Args:
            text: 待检测文本
            output_path: HTML 报告保存路径
            title: 报告标题

        Returns:
            CheckResult 对象
        """
        from antihall.report.html_report import save_html_report

        result = self.check(text)
        save_html_report(result, output_path, title)
        return result
