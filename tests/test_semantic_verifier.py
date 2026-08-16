# -*- coding: utf-8 -*-
"""Test the semantic verifier with mock data sources."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from antihall.models import (
    ClaimReport,
    Evidence,
    FinancialClaim,
    SemanticClaim,
    SemanticType,
    Verdict,
)
from antihall.verifier.semantic_verifier import SemanticVerifier
from antihall.models import ClaimType


class MockDataSource:
    """Mock data source that returns predefined evidence."""

    def __init__(self, evidence_map=None, trend_map=None):
        self._evidence_map = evidence_map or {}
        self._trend_map = trend_map or {}

    @property
    def is_available(self) -> bool:
        return True

    def get_evidence(self, entity, metric, year):
        key = (entity, metric, year)
        return self._evidence_map.get(key)

    def _resolve_stock_code(self, entity):
        return "600519"


def test_trend_reversal_hallucinated():
    """Test that declining data + 'growth' claim = hallucination."""
    # Entity data shows declining revenue
    ds = MockDataSource(
        trend_map=None,
        evidence_map={
            ("\u8d35\u5dde\u8305\u53f0", "\u8425\u6536", 2021): Evidence(
                source_name="mock", entity="\u8d35\u5dde\u8305\u53f0", metric="\u8425\u6536",
                actual_value=1200, unit="\u4ebf\u5143", year=2021,
            ),
            ("\u8d35\u5dde\u8305\u53f0", "\u8425\u6536", 2022): Evidence(
                source_name="mock", entity="\u8d35\u5dde\u8305\u53f0", metric="\u8425\u6536",
                actual_value=1100, unit="\u4ebf\u5143", year=2022,
            ),
            ("\u8d35\u5dde\u8305\u53f0", "\u8425\u6536", 2023): Evidence(
                source_name="mock", entity="\u8d35\u5dde\u8305\u53f0", metric="\u8425\u6536",
                actual_value=1000, unit="\u4ebf\u5143", year=2023,
            ),
        },
    )

    claim = SemanticClaim(
        raw_text="\u8d35\u5dde\u8305\u53f0\u8425\u6536\u8fde\u7eed\u4e09\u5e74\u589e\u957f",
        entity="\u8d35\u5dde\u8305\u53f0",
        semantic_type=SemanticType.TREND_REVERSAL,
        claim_text="\u8425\u6536\u8fde\u7eed\u4e09\u5e74\u589e\u957f",
        claimed_direction="\u589e\u957f",
        claimed_period="\u8fde\u7eed\u4e09\u5e74",
    )

    # Patch _fetch_trend to use our mock evidence_map
    verifier = SemanticVerifier(datasource=ds)
    original_fetch = verifier._fetch_trend
    def mock_fetch(entity, metric, num_years):
        result = []
        for year in [2021, 2022, 2023]:
            ev = ds.get_evidence(entity, metric, year)
            if ev and ev.actual_value is not None:
                result.append({"year": year, "value": ev.actual_value})
        return result
    verifier._fetch_trend = mock_fetch

    report = verifier.verify(claim)

    assert report.verdict == Verdict.HALLUCINATED
    assert "\u8d8b\u52bf\u98a0\u5012" in report.explanation  # 趋势颠倒


def test_trend_correct():
    """Test that increasing data + 'growth' claim = correct."""
    ds = MockDataSource(
        evidence_map={
            ("\u6bd4\u4e9a\u8fea", "\u8425\u6536", 2021): Evidence(
                source_name="mock", entity="\u6bd4\u4e9a\u8fea", metric="\u8425\u6536",
                actual_value=1000, unit="\u4ebf\u5143", year=2021,
            ),
            ("\u6bd4\u4e9a\u8fea", "\u8425\u6536", 2022): Evidence(
                source_name="mock", entity="\u6bd4\u4e9a\u8fea", metric="\u8425\u6536",
                actual_value=3000, unit="\u4ebf\u5143", year=2022,
            ),
            ("\u6bd4\u4e9a\u8fea", "\u8425\u6536", 2023): Evidence(
                source_name="mock", entity="\u6bd4\u4e9a\u8fea", metric="\u8425\u6536",
                actual_value=6000, unit="\u4ebf\u5143", year=2023,
            ),
        },
    )

    claim = SemanticClaim(
        raw_text="\u6bd4\u4e9a\u8fea\u8425\u6536\u8fde\u7eed\u4e09\u5e74\u589e\u957f",
        entity="\u6bd4\u4e9a\u8fea",
        semantic_type=SemanticType.TREND_REVERSAL,
        claim_text="\u8425\u6536\u8fde\u7eed\u4e09\u5e74\u589e\u957f",
        claimed_direction="\u589e\u957f",
        claimed_period="\u8fde\u7eed\u4e09\u5e74",
    )

    verifier = SemanticVerifier(datasource=ds)
    def mock_fetch(entity, metric, num_years):
        result = []
        for year in [2021, 2022, 2023]:
            ev = ds.get_evidence(entity, metric, year)
            if ev and ev.actual_value is not None:
                result.append({"year": year, "value": ev.actual_value})
        return result
    verifier._fetch_trend = mock_fetch

    report = verifier.verify(claim)

    assert report.verdict == Verdict.CORRECT


def test_metric_confusion_hallucinated():
    """Test: text says 'net profit 1500B' but 1500B is actually revenue."""
    ds = MockDataSource(
        evidence_map={
            ("\u8d35\u5dde\u8305\u53f0", "\u51c0\u5229\u6da6", 2023): Evidence(
                source_name="mock", entity="\u8d35\u5dde\u8305\u53f0", metric="\u51c0\u5229\u6da6",
                actual_value=600, unit="\u4ebf\u5143", year=2023,
            ),
            ("\u8d35\u5dde\u8305\u53f0", "\u8425\u6536", 2023): Evidence(
                source_name="mock", entity="\u8d35\u5dde\u8305\u53f0", metric="\u8425\u6536",
                actual_value=1500, unit="\u4ebf\u5143", year=2023,
            ),
        },
    )

    claim = SemanticClaim(
        raw_text="\u8d35\u5dde\u8305\u53f0 2023 \u5e74\u51c0\u5229\u6da6 1500 \u4ebf\u5143",
        entity="\u8d35\u5dde\u8305\u53f0",
        semantic_type=SemanticType.METRIC_CONFUSION,
        claim_text="\u51c0\u5229\u6da6 1500 \u4ebf\u5143",
        claimed_metric="\u51c0\u5229\u6da6",
        actual_metric="",
        year=2023,
    )

    verifier = SemanticVerifier(datasource=ds)
    report = verifier.verify(claim)

    assert report.verdict == Verdict.HALLUCINATED
    assert "\u6307\u6807\u6df7\u6dc6" in report.explanation  # 指标混淆


def test_no_datasource_unverifiable():
    """Test that semantic verifier returns unverifiable without datasource."""
    verifier = SemanticVerifier(datasource=None)

    claim = SemanticClaim(
        raw_text="\u8425\u6536\u589e\u957f",
        entity="\u8d35\u5dde\u8305\u53f0",
        semantic_type=SemanticType.TREND_REVERSAL,
        claim_text="\u8425\u6536\u589e\u957f",
        claimed_direction="\u589e\u957f",
    )

    report = verifier.verify(claim)
    assert report.verdict == Verdict.UNVERIFIABLE


if __name__ == "__main__":
    test_trend_reversal_hallucinated()
    test_trend_correct()
    test_metric_confusion_hallucinated()
    test_no_datasource_unverifiable()
    print("All tests passed!")
