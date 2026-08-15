"""测试 claim_extractor — 金融声明提取。"""
import sys
import os

# 让测试可以直接运行
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from antihall.extractor.claim_extractor import ClaimExtractor, normalize_to_yi
from antihall.models import ClaimType


def test_extract_revenue():
    """测试营收声明提取。"""
    extractor = ClaimExtractor()
    claims = extractor.extract("贵州茅台2023年营收1505.6亿元。")

    assert len(claims) == 1
    c = claims[0]
    assert c.entity == "贵州茅台"
    assert c.metric == "营收"
    assert c.value == 1505.6
    assert c.unit == "亿元"
    assert c.year == 2023
    assert c.claim_type == ClaimType.REVENUE


def test_extract_net_profit():
    """测试净利润声明提取。"""
    extractor = ClaimExtractor()
    claims = extractor.extract("比亚迪2023年净利润300.4亿元。")

    assert len(claims) == 1
    c = claims[0]
    assert c.entity == "比亚迪"
    assert c.metric == "净利润"
    assert c.value == 300.4
    assert c.unit == "亿元"
    assert c.year == 2023
    assert c.claim_type == ClaimType.NET_PROFIT


def test_extract_multiple_claims():
    """测试多句提取。"""
    extractor = ClaimExtractor()
    text = "贵州茅台2023年营收1505.6亿元。比亚迪2023年净利润300.4亿元。"
    claims = extractor.extract(text)

    assert len(claims) == 2
    assert claims[0].entity == "贵州茅台"
    assert claims[1].entity == "比亚迪"


def test_extract_growth_rate():
    """测试增长率提取。"""
    extractor = ClaimExtractor()
    claims = extractor.extract("宁德时代2023年净利润同比增长43.6%。")

    assert len(claims) == 1
    c = claims[0]
    assert c.entity == "宁德时代"
    assert c.value == 43.6
    assert c.unit == "%"
    assert c.year == 2023


def test_extract_gross_margin():
    """测试毛利率提取。"""
    extractor = ClaimExtractor()
    claims = extractor.extract("恒瑞医药2023年毛利率85%。")

    assert len(claims) == 1
    c = claims[0]
    assert c.metric == "毛利率"
    assert c.value == 85.0
    assert c.unit == "%"


def test_normalize_to_yi():
    """测试单位换算。"""
    assert normalize_to_yi(1, "万亿元") == 10000.0
    assert normalize_to_yi(1.5, "亿元") == 1.5
    assert normalize_to_yi(500, "万元") == 0.05
    assert normalize_to_yi(50, "%") == 50.0


def test_no_claim():
    """测试无声明文本。"""
    extractor = ClaimExtractor()
    claims = extractor.extract("今天天气不错。")
    assert len(claims) == 0


if __name__ == "__main__":
    test_extract_revenue()
    test_extract_net_profit()
    test_extract_multiple_claims()
    test_extract_growth_rate()
    test_extract_gross_margin()
    test_normalize_to_yi()
    test_no_claim()
    print("All tests passed!")
