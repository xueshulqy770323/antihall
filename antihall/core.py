# -*- coding: utf-8 -*-
"""HallucinationChecker - antihall v3 main interface.

v3.0 adds:
- LLM-powered semantic claim extraction (optional, needs API key)
- Semantic hallucination detection (trend reversal, temporal mismatch,
  metric confusion, causal fabrication)
- Unified pipeline that merges regex + LLM extraction

Usage without LLM (regex-only, free, no API key):

    from antihall import HallucinationChecker

    checker = HallucinationChecker()
    result = checker.check("...")
    print(result.summary())

Usage with LLM (full power, needs API key):

    from antihall import HallucinationChecker
    from antihall.llm.client import LLMConfig

    checker = HallucinationChecker(
        llm_config=LLMConfig(
            api_key="sk-xxx",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        )
    )
    result = checker.check("...")
    print(result.summary())
"""
from __future__ import annotations

import logging
from typing import Optional

from antihall.models import CheckResult, ClaimReport
from antihall.pipeline import DetectionPipeline
from antihall.datasource.akshare_source import AKShareDataSource
from antihall.llm.client import LLMClient, LLMConfig

logger = logging.getLogger(__name__)


class HallucinationChecker:
    """Financial report hallucination checker - main interface.

    Two modes:
    1. Regex-only (default, no API key): numeric claim extraction + verification
    2. Full mode (with LLM): adds semantic extraction + verification
    """

    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        datasource: Optional[AKShareDataSource] = None,
        use_llm: bool = True,
    ):
        llm_client = None
        if llm_config and llm_config.api_key:
            llm_client = LLMClient(llm_config)
            logger.info(
                f"LLM enabled: model={llm_config.model}, "
                f"base_url={llm_config.base_url}"
            )
        else:
            logger.info("LLM not configured, running in regex-only mode")

        self.pipeline = DetectionPipeline(
            datasource=datasource,
            llm_client=llm_client,
            use_llm=use_llm,
        )

    def check(self, text: str) -> CheckResult:
        """Detect hallucinations in a Chinese financial text.

        Args:
            text: Chinese financial text to check.

        Returns:
            CheckResult with all claims, verdicts, explanations, evidence.
        """
        return self.pipeline.run(text)

    def check_and_report(
        self,
        text: str,
        output_path: str,
        title: str = "",
    ) -> CheckResult:
        """Detect hallucinations and save an HTML report.

        Args:
            text: Text to check.
            output_path: Path to save the HTML report.
            title: Report title.

        Returns:
            CheckResult (also saved as HTML).
        """
        from antihall.report.html_report import save_html_report

        result = self.check(text)
        save_html_report(result, output_path, title)
        return result

    @property
    def llm_enabled(self) -> bool:
        """Whether LLM-powered detection is active."""
        return self.pipeline.llm_extractor is not None
