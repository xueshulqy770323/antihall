# -*- coding: utf-8 -*-
"""Test HTML report generation."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from antihall.models import (
    ClaimType,
    CheckResult,
    ClaimReport,
    Evidence,
    FinancialClaim,
    Verdict,
)
from antihall.report.html_report import generate_html_report


def test_generate_html_basic():
    """Test basic HTML report generation."""
    result = CheckResult(input_text="\u8d35\u5dde\u8305\u53f0 2023 \u5e74\u8425\u6536 2000 \u4ebf\u5143\u3002")

    claim = FinancialClaim(
        raw_text="\u8d35\u5dde\u8305\u53f0 2023 \u5e74\u8425\u6536 2000 \u4ebf\u5143",
        entity="\u8d35\u5dde\u8305\u53f0",
        metric="\u8425\u6536",
        value=2000.0,
        unit="\u4ebf\u5143",
        year=2023,
        claim_type=ClaimType.REVENUE,
    )
    evidence = Evidence(
        source_name="AKShare-\u5e74\u62a5",
        entity="\u8d35\u5dde\u8305\u53f0",
        metric="\u8425\u6536",
        actual_value=1505.6,
        unit="\u4ebf\u5143",
        year=2023,
        url="https://example.com",
    )

    report = ClaimReport(
        claim=claim,
        evidence=evidence,
        verdict=Verdict.HALLUCINATED,
        deviation=0.329,
        explanation="\u6570\u5b57\u5e7b\u89c9\u3002\u6587\u672c\u79f0 2000 \u4ebf\u5143\uff0c\u5b9e\u9645 1505.6 \u4ebf\u5143\u3002",
        suggestion="\u5efa\u8bae\u4fee\u6539\u4e3a\uff1a\u8d35\u5dde\u8305\u53f0 2023 \u5e74\u8425\u6536 1505.6 \u4ebf\u5143\u3002",
    )
    result.claims = [report]

    html = generate_html_report(result, "\u6d4b\u8bd5\u62a5\u544a")
    assert "<html" in html
    assert "1505.6" in html
    assert "example.com" in html


def test_generate_html_empty():
    """Test empty result HTML report."""
    result = CheckResult(input_text="No claims here.")
    html = generate_html_report(result)
    assert "<html" in html
    assert "0" in html


if __name__ == "__main__":
    test_generate_html_basic()
    test_generate_html_empty()
    print("All tests passed!")
