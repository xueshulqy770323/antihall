"""测试 explainer — 解释器和结果摘要。"""
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
from antihall.explainer.explainer import Explainer
from antihall.verifier.numeric_verifier import NumericVerifier


def test_explain_hallucinated():
    """测试幻觉声明的解释。"""
    explainer = Explainer()
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
        url="https://emweb.securities.eastmoney.com/...",
    )

    report = verifier.verify(claim, evidence)
    report = explainer.explain(report)

    assert report.verdict == Verdict.HALLUCINATED
    assert "幻觉" in report.explanation
    assert "1505.6" in report.suggestion
    assert "2000" not in report.suggestion  # 建议中不应出现错误数值


def test_explain_correct():
    """测试正确声明的解释。"""
    explainer = Explainer()

    claim = FinancialClaim(
        raw_text="贵州茅台2023年营收1505.6亿元",
        entity="贵州茅台",
        metric="营收",
        value=1505.6,
        unit="亿元",
        year=2023,
    )
    evidence = Evidence(
        source_name="AKShare-年报",
        entity="贵州茅台",
        metric="营收",
        actual_value=1505.6,
        unit="亿元",
        year=2023,
    )

    verifier = NumericVerifier()
    report = verifier.verify(claim, evidence)
    report = explainer.explain(report)

    assert report.verdict == Verdict.CORRECT
    assert "核查通过" in report.explanation


def test_explain_unverifiable():
    """测试无法验证的解释。"""
    explainer = Explainer()

    claim = FinancialClaim(
        raw_text="某公司2023年营收100亿元",
        entity="",
        metric="营收",
        value=100.0,
        unit="亿元",
        year=2023,
    )

    verifier = NumericVerifier()
    report = verifier.verify(claim, None)
    report = explainer.explain(report)

    assert report.verdict == Verdict.UNVERIFIABLE
    assert "无法验证" in report.explanation


def test_check_result_summary():
    """测试 CheckResult 摘要统计。"""
    result = CheckResult(input_text="test")

    # 构造两条报告：1幻觉 + 1正确
    result.claims = [
        ClaimReport(
            claim=FinancialClaim(
                raw_text="a", entity="A", metric="营收",
                value=100, unit="亿元", year=2023,
            ),
            verdict=Verdict.HALLUCINATED,
        ),
        ClaimReport(
            claim=FinancialClaim(
                raw_text="b", entity="B", metric="营收",
                value=200, unit="亿元", year=2023,
            ),
            verdict=Verdict.CORRECT,
        ),
    ]

    assert result.total_claims == 2
    assert result.hallucinated_count == 1
    assert result.correct_count == 1
    assert result.hallucination_rate == 0.5
    assert result.risk_level == "高风险"
    assert "2 条声明" in result.summary()


if __name__ == "__main__":
    test_explain_hallucinated()
    test_explain_correct()
    test_explain_unverifiable()
    test_check_result_summary()
    print("All tests passed!")
