"""测试 verifier — 数字核查引擎。"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from antihall.models import (
    ClaimType,
    Evidence,
    FinancialClaim,
    Verdict,
)
from antihall.verifier.numeric_verifier import NumericVerifier


def test_verify_correct():
    """测试正确数值。"""
    verifier = NumericVerifier()

    claim = FinancialClaim(
        raw_text="贵州茅台2023年营收1505.6亿元",
        entity="贵州茅台",
        metric="营收",
        value=1505.6,
        unit="亿元",
        year=2023,
        claim_type=ClaimType.REVENUE,
    )
    evidence = Evidence(
        source_name="AKShare-年报",
        entity="贵州茅台",
        metric="营收",
        actual_value=1505.6,
        unit="亿元",
        year=2023,
    )

    report = verifier.verify(claim, evidence)
    assert report.verdict == Verdict.CORRECT
    assert report.deviation is not None
    assert abs(report.deviation) < 0.02  # 2% 容差内


def test_verify_hallucinated():
    """测试幻觉数值。"""
    verifier = NumericVerifier()

    claim = FinancialClaim(
        raw_text="贵州茅台2023年营收2000亿元",
        entity="贵州茅台",
        metric="营收",
        value=2000.0,
        unit="亿元",
        year=2023,
        claim_type=ClaimType.REVENUE,
    )
    evidence = Evidence(
        source_name="AKShare-年报",
        entity="贵州茅台",
        metric="营收",
        actual_value=1505.6,
        unit="亿元",
        year=2023,
    )

    report = verifier.verify(claim, evidence)
    assert report.verdict == Verdict.HALLUCINATED
    assert report.deviation is not None
    assert report.deviation > 0.02  # 超出容差


def test_verify_ratio_correct():
    """测试比率指标正确。"""
    verifier = NumericVerifier()

    claim = FinancialClaim(
        raw_text="恒瑞医药2023年毛利率85%",
        entity="恒瑞医药",
        metric="毛利率",
        value=85.0,
        unit="%",
        year=2023,
        claim_type=ClaimType.GROSS_MARGIN,
    )
    evidence = Evidence(
        source_name="AKShare-年报",
        entity="恒瑞医药",
        metric="毛利率",
        actual_value=84.5,
        unit="%",
        year=2023,
    )

    report = verifier.verify(claim, evidence)
    assert report.verdict == Verdict.CORRECT  # 0.5个百分点 < 1容差


def test_verify_unverifiable():
    """测试无证据时标记为无法验证。"""
    verifier = NumericVerifier()

    claim = FinancialClaim(
        raw_text="某公司2023年营收100亿元",
        entity="某公司",
        metric="营收",
        value=100.0,
        unit="亿元",
        year=2023,
    )

    report = verifier.verify(claim, None)
    assert report.verdict == Verdict.UNVERIFIABLE


def test_verify_unit_conversion():
    """测试不同单位间的比较。"""
    verifier = NumericVerifier()

    # 声称 1.5 万亿元，实际 15000 亿元 → 应该一致
    claim = FinancialClaim(
        raw_text="工商银行2023年营收1.5万亿元",
        entity="工商银行",
        metric="营收",
        value=1.5,
        unit="万亿元",
        year=2023,
        claim_type=ClaimType.REVENUE,
    )
    evidence = Evidence(
        source_name="AKShare-年报",
        entity="工商银行",
        metric="营收",
        actual_value=15000,
        unit="亿元",
        year=2023,
    )

    report = verifier.verify(claim, evidence)
    assert report.verdict == Verdict.CORRECT


if __name__ == "__main__":
    test_verify_correct()
    test_verify_hallucinated()
    test_verify_ratio_correct()
    test_verify_unverifiable()
    test_verify_unit_conversion()
    print("All tests passed!")
