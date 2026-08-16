# -*- coding: utf-8 -*-
"""Semantic hallucination verifier — detects meaning-level fabrications.

Unlike NumericVerifier (which just compares two numbers), SemanticVerifier
checks four types of semantic hallucinations:

1. Trend reversal: text says "growing" but data shows "declining"
   - Needs multi-year data from AKShare
   - Verifies by checking the actual trend direction

2. Temporal mismatch: text attributes a number to the wrong year
   - Extract the number + claimed year
   - Look up which year the number actually belongs to
   - Flag if the number matches a different year

3. Metric confusion: text says "net profit 1500B" but 1500B is revenue
   - Extract the claimed metric + value
   - Look up the actual metric that has this value
   - Flag if the value matches a different metric

4. Causal fabrication: text claims a cause-effect relationship
   - "Raw material prices fell, so gross margin rose"
   - Verify: did raw material prices actually fall? Did margin actually rise?
   - This is the hardest to verify automatically and may use LLM judgment
"""
from __future__ import annotations

import logging
from typing import Optional

from antihall.models import (
    ClaimReport,
    Evidence,
    FinancialClaim,
    SemanticClaim,
    SemanticType,
    Verdict,
)
from antihall.extractor.claim_extractor import normalize_to_yi

logger = logging.getLogger(__name__)


class SemanticVerifier:
    """Verifies semantic claims against real financial data."""

    def __init__(self, datasource=None, llm_client=None):
        """
        Args:
            datasource: AKShareDataSource instance for fetching real data.
            llm_client: Optional LLMClient for causal verification (which
                        requires reasoning over cause-effect statements).
        """
        self.datasource = datasource
        self.llm_client = llm_client

    def verify(
        self,
        claim: SemanticClaim,
    ) -> ClaimReport:
        """Verify a single semantic claim.

        Args:
            claim: A SemanticClaim to verify.

        Returns:
            ClaimReport with verdict, explanation, and suggestion.
        """
        report = ClaimReport(
            claim=claim,
            semantic_type=claim.semantic_type,
        )

        if claim.semantic_type == SemanticType.TREND_REVERSAL:
            return self._verify_trend(claim, report)
        elif claim.semantic_type == SemanticType.TEMPORAL_MISMATCH:
            return self._verify_temporal(claim, report)
        elif claim.semantic_type == SemanticType.METRIC_CONFUSION:
            return self._verify_metric_confusion(claim, report)
        elif claim.semantic_type == SemanticType.CAUSAL:
            return self._verify_causal(claim, report)
        else:
            report.verdict = Verdict.ERROR
            report.explanation = f"Unknown semantic type: {claim.semantic_type}"
            return report

    # ------------------------------------------------------------------- #
    # 1. Trend reversal verification
    # ------------------------------------------------------------------- #

    def _verify_trend(self, claim: SemanticClaim, report: ClaimReport) -> ClaimReport:
        """Verify trend claims by checking multi-year data.

        Example:
            Claim: "XX公司营收连续三年增长"
            Check: fetch 3 years of revenue data, verify they're all increasing
        """
        if not self.datasource or not self.datasource.is_available:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg("\u6570\u636e\u6e90\u4e0d\u53ef\u7528")
            return report

        # Determine the metric and entity
        entity = claim.entity
        metric = self._infer_metric_from_text(claim.claim_text)

        if not entity or not metric:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg(
                "\u65e0\u6cd5\u8bc6\u522b\u516c\u53f8\u6216\u6307\u6807"
            )
            return report

        # Determine how many years to check
        num_years = self._parse_period_years(claim.claimed_period) or 3

        # Fetch trend data
        trend_data = self._fetch_trend(entity, metric, num_years)

        if not trend_data or len(trend_data) < 2:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg(
                f"\u65e0\u6cd5\u83b7\u53d6{entity}\u8fd1{num_years}\u5e74\u7684{metric}\u6570\u636e"
            )
            return report

        # Check trend direction
        claimed_direction = claim.claimed_direction
        actual_is_increasing = self._is_increasing(trend_data)

        # Build evidence
        report.evidence = Evidence(
            source_name="AKShare-\u5e74\u62a5",
            entity=entity,
            metric=metric,
            trend_data=trend_data,
            url=self._build_evidence_url(entity),
        )

        # Determine verdict
        if claimed_direction in ("\u589e\u957f", "\u4e0a\u5347", "\u63d0\u5347"):
            if actual_is_increasing:
                report.verdict = Verdict.CORRECT
                report.explanation = (
                    f"\u8d8b\u52bf\u6838\u67e5\u901a\u8fc7\u3002{entity}\u7684{metric}"
                    f"\u786e\u5b9e\u5728\u8fd1{num_years}\u5e74\u5448\u4e0a\u5347\u8d8b\u52bf\u3002"
                )
            else:
                report.verdict = Verdict.HALLUCINATED
                report.explanation = (
                    f"\u8d8b\u52bf\u98a0\u5012\u3002\u6587\u672c\u79f0{entity}\u7684{metric}"
                    f"{claim.claimed_direction}\uff0c\u4f46\u5b9e\u9645\u6570\u636e\u663e\u793a"
                    f"\u8fd1{num_years}\u5e74\u8d8b\u52bf\u4e3a\u4e0b\u964d\u3002"
                )
        elif claimed_direction in ("\u4e0b\u964d", "\u4e0b\u6ed1", "\u51cf\u5c11"):
            if not actual_is_increasing:
                report.verdict = Verdict.CORRECT
                report.explanation = (
                    f"\u8d8b\u52bf\u6838\u67e5\u901a\u8fc7\u3002{entity}\u7684{metric}"
                    f"\u786e\u5b9e\u5728\u8fd1{num_years}\u5e74\u5448\u4e0b\u964d\u8d8b\u52bf\u3002"
                )
            else:
                report.verdict = Verdict.HALLUCINATED
                report.explanation = (
                    f"\u8d8b\u52bf\u98a0\u5012\u3002\u6587\u672c\u79f0{entity}\u7684{metric}"
                    f"{claim.claimed_direction}\uff0c\u4f46\u5b9e\u9645\u6570\u636e\u663e\u793a"
                    f"\u8fd1{num_years}\u5e74\u8d8b\u52bf\u4e3a\u4e0a\u5347\u3002"
                )
        else:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg(
                f"\u65e0\u6cd5\u8bc6\u522b\u58f0\u79f0\u7684\u8d8b\u52bf\u65b9\u5411: {claimed_direction}"
            )

        return report

    # ------------------------------------------------------------------- #
    # 2. Temporal mismatch verification
    # ------------------------------------------------------------------- #

    def _verify_temporal(self, claim: SemanticClaim, report: ClaimReport) -> ClaimReport:
        """Verify temporal mismatch: number attributed to wrong year.

        Logic:
            1. Extract the claimed year and number value from the claim
            2. Fetch data for the claimed year and adjacent years
            3. Check if the number matches a different year's data
        """
        if not self.datasource or not self.datasource.is_available:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg("\u6570\u636e\u6e90\u4e0d\u53ef\u7528")
            return report

        claimed_year = claim.claimed_year
        entity = claim.entity
        metric = self._infer_metric_from_text(claim.claim_text)

        if not claimed_year or not entity or not metric:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg(
                "\u65e0\u6cd5\u8bc6\u522b\u5e74\u4efd\u3001\u516c\u53f8\u6216\u6307\u6807"
            )
            return report

        # Extract the numeric value from the raw text
        value = self._extract_number(claim.raw_text)
        if value is None:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg(
                "\u65e0\u6cd5\u4ece\u6587\u672c\u4e2d\u63d0\u53d6\u6570\u503c"
            )
            return report

        # Check the claimed year first
        ev_claimed = self.datasource.get_evidence(entity, metric, claimed_year)
        if ev_claimed and ev_claimed.actual_value is not None:
            claim_normalized = normalize_to_yi(value, "\u4ebf\u5143")  # assume 亿元
            actual_normalized = normalize_to_yi(
                ev_claimed.actual_value, ev_claimed.unit
            )
            if self._values_match(claim_normalized, actual_normalized):
                report.verdict = Verdict.CORRECT
                report.evidence = ev_claimed
                report.explanation = (
                    f"\u65f6\u95f4\u6838\u67e5\u901a\u8fc7\u3002"
                    f"{entity}{claimed_year}\u5e74\u7684{metric}"
                    f"\u786e\u5b9e\u63a5\u8fd1{value}\u4ebf\u5143\u3002"
                )
                return report

        # Check adjacent years
        for offset in [-1, 1, -2, 2]:
            check_year = claimed_year + offset
            ev = self.datasource.get_evidence(entity, metric, check_year)
            if ev and ev.actual_value is not None:
                actual_normalized = normalize_to_yi(ev.actual_value, ev.unit)
                if self._values_match(normalize_to_yi(value, "\u4ebf\u5143"), actual_normalized):
                    report.verdict = Verdict.HALLUCINATED
                    report.evidence = ev
                    report.explanation = (
                        f"\u65f6\u95f4\u9519\u4f4d\u3002\u6587\u672c\u79f0"
                        f"{entity}{claimed_year}\u5e74\u7684{metric}\u4e3a{value}\u4ebf\u5143\uff0c"
                        f"\u4f46\u8be5\u6570\u5b57\u5b9e\u9645\u662f{check_year}\u5e74\u7684\u6570\u636e\u3002"
                    )
                    report.suggestion = (
                        f"\u5efa\u8bae\u4fee\u6539\u4e3a\uff1a{entity}{check_year}\u5e74"
                        f"\u7684{metric}\u4e3a{ev.actual_value}{ev.unit}\u3002"
                    )
                    return report

        report.verdict = Verdict.UNVERIFIABLE
        report.explanation = self._unverifiable_msg(
            "\u65e0\u6cd5\u786e\u8ba4\u8be5\u6570\u5b57\u5c5e\u4e8e\u54ea\u4e00\u5e74"
        )
        return report

    # ------------------------------------------------------------------- #
    # 3. Metric confusion verification
    # ------------------------------------------------------------------- #

    def _verify_metric_confusion(
        self, claim: SemanticClaim, report: ClaimReport
    ) -> ClaimReport:
        """Verify metric confusion: number attributed to wrong metric.

        Logic:
            1. The claim says "metric A = value X"
            2. Look up metric A for that year — does it match X?
            3. If not, look up other metrics (revenue, profit, margin)
               to see if X matches one of them
            4. If X matches metric B but not A → metric confusion hallucination
        """
        if not self.datasource or not self.datasource.is_available:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg("\u6570\u636e\u6e90\u4e0d\u53ef\u7528")
            return report

        entity = claim.entity
        claimed_metric = claim.claimed_metric or self._infer_metric_from_text(claim.claim_text)
        value = self._extract_number(claim.raw_text)
        year = claim.year or claim.claimed_year

        if not all([entity, claimed_metric, value, year]):
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg(
                "\u4fe1\u606f\u4e0d\u5168\uff0c\u65e0\u6cd5\u6838\u67e5"
            )
            return report

        # Check if the claimed metric has this value
        ev_claimed = self.datasource.get_evidence(entity, claimed_metric, year)
        if ev_claimed and ev_claimed.actual_value is not None:
            if self._values_match(value, normalize_to_yi(ev_claimed.actual_value, ev_claimed.unit)):
                # Value matches the claimed metric — no confusion
                report.verdict = Verdict.CORRECT
                report.evidence = ev_claimed
                report.explanation = (
                    f"\u6307\u6807\u6838\u67e5\u901a\u8fc7\u3002"
                    f"{entity}{year}\u5e74\u7684{claimed_metric}"
                    f"\u786e\u5b9e\u63a5\u8fd1{value}\u4ebf\u5143\u3002"
                )
                return report

        # Try other metrics to find a match
        other_metrics = [
            "\u8425\u6536", "\u51c0\u5229\u6da6", "\u6bdb\u5229\u7387",
            "\u51c0\u5229\u7387", "\u8d44\u4ea7\u8d1f\u503a\u7387",
        ]
        for other_metric in other_metrics:
            if other_metric == claimed_metric:
                continue
            ev = self.datasource.get_evidence(entity, other_metric, year)
            if ev and ev.actual_value is not None:
                if self._values_match(value, normalize_to_yi(ev.actual_value, ev.unit)):
                    report.verdict = Verdict.HALLUCINATED
                    report.evidence = ev
                    report.explanation = (
                        f"\u6307\u6807\u6df7\u6dc6\u3002\u6587\u672c\u79f0"
                        f"{entity}{year}\u5e74\u7684{claimed_metric}\u4e3a{value}\u4ebf\u5143\uff0c"
                        f"\u4f46\u8be5\u6570\u5b57\u5b9e\u9645\u662f{other_metric}\u7684\u6570\u636e\u3002"
                    )
                    report.suggestion = (
                        f"\u5efa\u8bae\u4fee\u6539\u4e3a\uff1a{entity}{year}\u5e74"
                        f"\u7684{other_metric}\u4e3a{ev.actual_value}{ev.unit}\u3002"
                    )
                    return report

        report.verdict = Verdict.UNVERIFIABLE
        report.explanation = self._unverifiable_msg(
            "\u65e0\u6cd5\u786e\u8ba4\u8be5\u6570\u5b57\u5c5e\u4e8e\u54ea\u4e2a\u6307\u6807"
        )
        return report

    # ------------------------------------------------------------------- #
    # 4. Causal verification (LLM-assisted)
    # ------------------------------------------------------------------- #

    def _verify_causal(self, claim: SemanticClaim, report: ClaimReport) -> ClaimReport:
        """Verify causal claims using LLM reasoning + data.

        Example:
            Claim: "因原材料降价，毛利率提升"
            Steps:
            1. Verify the effect: did gross margin actually increase?
            2. Verify the cause: can we find data on raw material prices?
            3. Use LLM to judge if the causal link is plausible

        This is the most complex verification and may use LLM judgment.
        """
        if not self.datasource or not self.datasource.is_available:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = self._unverifiable_msg("\u6570\u636e\u6e90\u4e0d\u53ef\u7528")
            return report

        entity = claim.entity
        effect_metric = self._infer_metric_from_text(claim.claimed_effect or claim.claim_text)
        cause_desc = claim.claimed_cause

        # Try to verify the effect (did it actually happen?)
        if effect_metric and entity:
            trend_data = self._fetch_trend(entity, effect_metric, 2)
            if trend_data and len(trend_data) >= 2:
                report.evidence = Evidence(
                    source_name="AKShare-\u5e74\u62a5",
                    entity=entity,
                    metric=effect_metric,
                    trend_data=trend_data,
                    url=self._build_evidence_url(entity),
                )
                # Check if effect is true
                latest = trend_data[-1]["value"]
                previous = trend_data[-2]["value"]
                effect_actually_happened = latest > previous

                if claim.claimed_effect and any(
                    kw in claim.claimed_effect for kw in ["\u63d0\u5347", "\u589e\u957f", "\u4e0a\u5347"]
                ):
                    if not effect_actually_happened:
                        report.verdict = Verdict.HALLUCINATED
                        report.explanation = (
                            f"\u56e0\u679c\u7f16\u9020\u3002\u6587\u672c\u79f0"
                            f"\u201c{cause_desc}\u201d\u5bfc\u81f4"
                            f"\u201c{claim.claimed_effect}\u201d\uff0c"
                            f"\u4f46\u5b9e\u9645\u6570\u636e\u663e\u793a"
                            f"{entity}\u7684{effect_metric}"
                            f"\u5e76\u672a\u63d0\u5347\uff08"
                            f"{trend_data[-2]['year']}\u5e74{previous}\u2192"
                            f"{trend_data[-1]['year']}\u5e74{latest}\uff09\u3002"
                        )
                        return report

        # If we can't fully verify the causal link, use LLM if available
        if self.llm_client and self.llm_client.is_available:
            return self._llm_causal_check(claim, report)

        # Can't verify — mark as unverifiable
        report.verdict = Verdict.UNVERIFIABLE
        report.explanation = (
            f"\u65e0\u6cd5\u5b8c\u5168\u9a8c\u8bc1\u56e0\u679c\u5173\u7cfb\u3002"
            f"\u58f0\u79f0\u201c{cause_desc}\u201d\u5bfc\u81f4"
            f"\u201c{claim.claimed_effect}\u201d\uff0c"
            f"\u5efa\u8bae\u4eba\u5de5\u6838\u67e5\u3002"
        )
        return report

    def _llm_causal_check(self, claim: SemanticClaim, report: ClaimReport) -> ClaimReport:
        """Use LLM to evaluate a causal claim's plausibility."""
        prompt = (
            f"\u8bf7\u5224\u65ad\u4ee5\u4e0b\u56e0\u679c\u5173\u7cfb\u662f\u5426\u5408\u7406\uff1a\n"
            f"\u539f\u6587: {claim.raw_text}\n"
            f"\u539f\u56e0: {claim.claimed_cause}\n"
            f"\u7ed3\u679c: {claim.claimed_effect}\n\n"
            f"\u8bf7\u53ea\u56de\u7b54 JSON: "
            f'{{"plausible": true/false, "reason": "\u7b80\u8981\u539f\u56e0"}}'
        )
        result = self.llm_client.chat_json(prompt)
        if isinstance(result, dict) and "plausible" in result:
            if result["plausible"]:
                report.verdict = Verdict.CORRECT
                report.explanation = (
                    f"\u56e0\u679c\u5173\u7cfb\u7ecfLLM\u5224\u65ad\u4e3a\u5408\u7406\u3002"
                    f"\u7406\u7531\uff1a{result.get('reason', '')}"
                )
            else:
                report.verdict = Verdict.HALLUCINATED
                report.explanation = (
                    f"\u56e0\u679c\u7f16\u9020\u3002"
                    f"\u201c{claim.claimed_cause}\u201d\u5bfc\u81f4"
                    f"\u201c{claim.claimed_effect}\u201d\u7684\u56e0\u679c\u5173\u7cfb"
                    f"\u7ecfLLM\u5224\u65ad\u4e3a\u4e0d\u5408\u7406\u3002"
                    f"\u7406\u7531\uff1a{result.get('reason', '')}"
                )
        else:
            report.verdict = Verdict.UNVERIFIABLE
            report.explanation = "\u56e0\u679c\u5173\u7cfb\u65e0\u6cd5\u5224\u65ad\u3002"

        return report

    # ------------------------------------------------------------------- #
    # Utility methods
    # ------------------------------------------------------------------- #

    @staticmethod
    def _infer_metric_from_text(text: str) -> str:
        """Guess the financial metric from text content."""
        metric_keywords = [
            ("\u8425\u4e1a\u6536\u5165", "\u8425\u6536"),
            ("\u8425\u6536", "\u8425\u6536"),
            ("\u51c0\u5229\u6da6", "\u51c0\u5229\u6da6"),
            ("\u6bdb\u5229\u7387", "\u6bdb\u5229\u7387"),
            ("\u51c0\u5229\u7387", "\u51c0\u5229\u7387"),
            ("ROE", "ROE"),
            ("\u8d44\u4ea7\u8d1f\u503a\u7387", "\u8d44\u4ea7\u8d1f\u503a\u7387"),
        ]
        for keyword, metric in metric_keywords:
            if keyword in text:
                return metric
        return ""

    @staticmethod
    def _parse_period_years(period: str) -> Optional[int]:
        """Parse a period string like '连续三年' into 3."""
        import re
        if not period:
            return None
        # Chinese numerals
        cn_map = {"\u4e00": 1, "\u4e8c": 2, "\u4e09": 3, "\u56db": 4, "\u4e94": 5,
                  "\u516d": 6, "\u4e03": 7, "\u516b": 8, "\u4e5d": 9, "\u5341": 10}
        for cn, num in cn_map.items():
            if cn in period:
                return num
        # Arabic numerals
        m = re.search(r"(\d+)\s*\u5e74", period)
        if m:
            return int(m.group(1))
        return None

    def _fetch_trend(self, entity: str, metric: str, num_years: int) -> list[dict]:
        """Fetch multiple years of data for trend analysis."""
        import datetime
        current_year = datetime.datetime.now().year
        trend = []
        for year in range(current_year - num_years, current_year):
            ev = self.datasource.get_evidence(entity, metric, year)
            if ev and ev.actual_value is not None:
                trend.append({"year": year, "value": ev.actual_value})
        return trend

    @staticmethod
    def _is_increasing(trend_data: list[dict]) -> bool:
        """Check if a trend is monotonically increasing."""
        if len(trend_data) < 2:
            return False
        values = [d["value"] for d in trend_data]
        return all(values[i] < values[i + 1] for i in range(len(values) - 1))

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        """Extract the first numeric value from text (in 亿元)."""
        import re
        # Match number + unit
        m = re.search(r"(\d+\.?\d*)\s*(\u4ebf\u5143|\u4e07\u5143|\u5143)", text)
        if m:
            value = float(m.group(1))
            unit = m.group(2)
            return normalize_to_yi(value, unit)
        # Match percentage
        m = re.search(r"(\d+\.?\d*)\s*%", text)
        if m:
            return float(m.group(1))
        return None

    @staticmethod
    def _values_match(a: float, b: float, tolerance: float = 0.05) -> bool:
        """Check if two values are close enough (within 5%)."""
        if a == 0 and b == 0:
            return True
        if a == 0 or b == 0:
            return False
        return abs(a - b) / max(abs(a), abs(b)) < tolerance

    def _build_evidence_url(self, entity: str) -> str:
        """Build evidence URL for an entity."""
        if self.datasource:
            code = self.datasource._resolve_stock_code(entity)
            if code:
                return f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code={code}"
        return ""

    @staticmethod
    def _unverifiable_msg(reason: str) -> str:
        return f"\u65e0\u6cd5\u9a8c\u8bc1\u3002\u539f\u56e0\uff1a{reason}\u3002"
