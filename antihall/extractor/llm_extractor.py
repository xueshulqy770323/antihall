# -*- coding: utf-8 -*-
"""LLM-powered semantic claim extractor.

Uses an LLM to extract both numeric and semantic claims from Chinese
financial text. Unlike the regex extractor, this understands:

- Numbers written in Chinese ("十五亿" → 15亿)
- Long-distance dependencies ("其营收...达到约1500亿")
- Causal assertions ("因原材料降价导致毛利率提升")
- Trend claims ("连续三年保持增长")
- Temporal references ("去年"/"上年同期")
- Metric confusions ("净利润1500亿" when 1500亿 is actually revenue)

Output: a list of FinancialClaim and SemanticClaim objects.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from antihall.llm.client import LLMClient, LLMConfig
from antihall.models import (
    AnyClaim,
    ClaimType,
    ExtractorMode,
    FinancialClaim,
    SemanticClaim,
    SemanticType,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Prompt templates
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = (
    "You are a financial claim extraction assistant for Chinese financial texts. "
    "Extract ALL verifiable claims from the given text. "
    "Output ONLY a JSON array, no markdown, no explanation.\n\n"
    "Each claim must be one of two types:\n"
    "1. Numeric claim: {\"type\": \"numeric\", \"raw_text\": \"...\", "
    "\"entity\": \"...\", \"metric\": \"...\", \"value\": number, "
    "\"unit\": \"...\", \"year\": number}\n"
    "2. Semantic claim: {\"type\": \"semantic\", \"raw_text\": \"...\", "
    "\"entity\": \"...\", \"semantic_type\": \"causal|trend_reversal|"
    "temporal_mismatch|metric_confusion\", \"claim_text\": \"...\", "
    "\"detail\": {\"key\": value}}\n\n"
    "Rules:\n"
    "- entity: company name (Chinese)\n"
    "- metric: one of 营收/净利润/毛利率/同比增长率/净利率/资产负债率/ROE\n"
    "- unit: 亿元/万元/%/万亿元\n"
    "- For causal: detail should have {\"cause\": \"...\", \"effect\": \"...\"}\n"
    "- For trend_reversal: detail should have {\"direction\": \"上升|下降|增长|下滑\", "
    "\"period\": \"连续N年\" or year range}\n"
    "- For temporal_mismatch: detail should have {\"claimed_year\": number, "
    "\"actual_year\": number}\n"
    "- For metric_confusion: detail should have {\"claimed_metric\": \"...\", "
    "\"actual_metric\": \"...\"}\n"
    "- If a sentence only states a plain number with no causal/trend/temporal/"
    "confusion aspect, extract it as numeric, not semantic.\n"
    "- Extract each claim from the most relevant sentence fragment.\n"
    "- Return [] if no claims found."
)


def _build_user_prompt(text: str) -> str:
    return f"Extract all financial claims from this text:\n\n{text}"


# Metric name to ClaimType mapping
_METRIC_TO_CLAIMTYPE = {
    "\u8425\u6536": ClaimType.REVENUE,
    "\u51c0\u5229\u6da6": ClaimType.NET_PROFIT,
    "\u6bdb\u5229\u7387": ClaimType.GROSS_MARGIN,
    "\u540c\u6bd4\u589e\u957f\u7387": ClaimType.GROWTH_RATE,
    "\u51c0\u5229\u7387": ClaimType.RATIO,
    "\u8d44\u4ea7\u8d1f\u503a\u7387": ClaimType.RATIO,
    "ROE": ClaimType.RATIO,
}

# Semantic type mapping
_SEM_TYPE_MAP = {
    "causal": SemanticType.CAUSAL,
    "trend_reversal": SemanticType.TREND_REVERSAL,
    "temporal_mismatch": SemanticType.TEMPORAL_MISMATCH,
    "metric_confusion": SemanticType.METRIC_CONFUSION,
}


class LLMClaimExtractor:
    """Extracts claims using an LLM for semantic understanding."""

    def __init__(self, client: LLMClient):
        self.client = client

    @property
    def is_available(self) -> bool:
        return self.client.is_available

    def extract(self, text: str) -> list[AnyClaim]:
        """Extract both numeric and semantic claims from text.

        Args:
            text: Chinese financial text.

        Returns:
            List of FinancialClaim and/or SemanticClaim objects.
        """
        if not self.is_available:
            logger.warning("LLM client not available (no API key), returning empty list")
            return []

        prompt = _build_user_prompt(text)
        result = self.client.chat_json(prompt, system=_SYSTEM_PROMPT)

        if isinstance(result, dict) and "error" in result:
            logger.error(f"LLM extraction failed: {result.get('raw', '')[:200]}")
            return []

        if not isinstance(result, list):
            logger.warning(f"Unexpected LLM response type: {type(result)}")
            return []

        claims: list[AnyClaim] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            claim = self._parse_claim(item)
            if claim:
                claims.append(claim)

        return claims

    def _parse_claim(self, item: dict) -> Optional[AnyClaim]:
        """Parse a single claim dict from LLM output."""
        claim_type_str = item.get("type", "")

        if claim_type_str == "numeric":
            return self._parse_numeric(item)
        elif claim_type_str == "semantic":
            return self._parse_semantic(item)
        else:
            logger.warning(f"Unknown claim type: {claim_type_str}")
            return None

    def _parse_numeric(self, item: dict) -> Optional[FinancialClaim]:
        """Parse a numeric claim from LLM output."""
        metric = item.get("metric", "")
        claim_type = _METRIC_TO_CLAIMTYPE.get(metric, ClaimType.OTHER)
        value = item.get("value")

        return FinancialClaim(
            raw_text=item.get("raw_text", ""),
            entity=item.get("entity", ""),
            metric=metric,
            value=float(value) if value is not None else None,
            unit=item.get("unit", ""),
            year=item.get("year"),
            claim_type=claim_type,
            source="",
            extractor=ExtractorMode.LLM,
        )

    def _parse_semantic(self, item: dict) -> Optional[SemanticClaim]:
        """Parse a semantic claim from LLM output."""
        sem_type_str = item.get("semantic_type", "")
        semantic_type = _SEM_TYPE_MAP.get(sem_type_str)
        if semantic_type is None:
            logger.warning(f"Unknown semantic type: {sem_type_str}")
            return None

        detail = item.get("detail", {})
        if not isinstance(detail, dict):
            detail = {}

        return SemanticClaim(
            raw_text=item.get("raw_text", ""),
            entity=item.get("entity", ""),
            semantic_type=semantic_type,
            claim_text=item.get("claim_text", ""),
            claimed_cause=detail.get("cause", ""),
            claimed_effect=detail.get("effect", ""),
            claimed_direction=detail.get("direction", ""),
            claimed_period=detail.get("period", ""),
            claimed_year=detail.get("claimed_year"),
            actual_year_data=detail.get("actual_year"),
            claimed_metric=detail.get("claimed_metric", ""),
            actual_metric=detail.get("actual_metric", ""),
            year=item.get("year"),
            extractor=ExtractorMode.LLM,
        )
