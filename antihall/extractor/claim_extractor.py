"""金融声明提取器 — 从中文金融文本中提取可验证的数字声明。

支持两种模式：
1. 正则模式（默认）：不依赖 LLM，用规则提取公司名+指标+数值+年份
2. LLM 模式（可选）：传入 LLM 客户端做更精准的语义提取
"""
from __future__ import annotations

import re
from typing import Optional

from antihall.models import FinancialClaim, ClaimType


# --------------------------------------------------------------------------- #
# 指标关键词 → 标准化指标名 + ClaimType
# --------------------------------------------------------------------------- #
METRIC_MAP: dict[str, tuple[str, ClaimType]] = {
    # 营收
    "营业收入": ("营收", ClaimType.REVENUE),
    "营收": ("营收", ClaimType.REVENUE),
    "总收入": ("营收", ClaimType.REVENUE),
    "营业收入": ("营收", ClaimType.REVENUE),
    # 净利润
    "净利润": ("净利润", ClaimType.NET_PROFIT),
    "归母净利润": ("归母净利润", ClaimType.NET_PROFIT),
    "股东净利润": ("归母净利润", ClaimType.NET_PROFIT),
    "扣非净利润": ("扣非净利润", ClaimType.NET_PROFIT),
    # 毛利率
    "毛利率": ("毛利率", ClaimType.GROSS_MARGIN),
    # 增长率
    "同比增长": ("同比增长率", ClaimType.GROWTH_RATE),
    "增速": ("同比增长率", ClaimType.GROWTH_RATE),
    "增幅": ("同比增长率", ClaimType.GROWTH_RATE),
    "增长率": ("同比增长率", ClaimType.GROWTH_RATE),
    "下降": ("同比增减率", ClaimType.GROWTH_RATE),
    "下滑": ("同比增减率", ClaimType.GROWTH_RATE),
    # 其他比率
    "净利率": ("净利率", ClaimType.RATIO),
    "资产负债率": ("资产负债率", ClaimType.RATIO),
    "ROE": ("ROE", ClaimType.RATIO),
    "研发费用率": ("研发费用率", ClaimType.RATIO),
}

# 公司名提取的正则：匹配 2-6 个汉字 + "股份"/"集团"/"科技"等后缀
_COMPANY_SUFFIXES = (
    r"(?:股份|集团|科技|控股|实业|能源|医药|生物|电子|半导体|新能源"
    r"|材料|化学食品|饮料|白酒|保险|银行|证券|汽车|重工|建设|电气"
    r"|通信|信息|软件|网络|机器|装备|航空|航天|农牧|渔业|林业)"
)
COMPANY_PATTERN = re.compile(
    rf"([\u4e00-\u9fff]{{2,8}}(?:{_COMPANY_SUFFIXES}(?:有限公司)?)?)"
)

# 年份
YEAR_PATTERN = re.compile(r"(\d{4})\s*年")

季度_PATTERN = re.compile(r"第?[一二三四1234]\s*季度")

# 数值+单位
NUMERIC_PATTERN = re.compile(
    r"([-+]?\d+\.?\d*)\s*"
    r"(万亿元|亿元|万元|元|%)"
)

# 单位转换到统一基准（亿元）
UNIT_TO_YI = {
    "万亿元": 10000,
    "亿元": 1,
    "万元": 0.0001,
    "元": 0.00000001,
}


class ClaimExtractor:
    """从中文金融文本中提取 FinancialClaim 列表。"""

    def extract(self, text: str) -> list[FinancialClaim]:
        """提取文本中所有可辨识的金融声明。

        Args:
            text: 中文金融文本，如 LLM 生成的财报分析。

        Returns:
            FinancialClaim 列表，可能为空。
        """
        claims: list[FinancialClaim] = []
        # 按句号/分号/换行切句
        sentences = re.split(r"[。；;\n！!？?]", text)

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            claim = self._extract_from_sentence(sent)
            if claim:
                claims.append(claim)

        return claims

    def _extract_from_sentence(self, sentence: str) -> Optional[FinancialClaim]:
        """从单句中提取一个声明。"""
        # 1. 识别指标
        metric_raw, claim_type = self._match_metric(sentence)
        if metric_raw is None:
            return None

        # 2. 识别公司名
        entity = self._match_company(sentence)

        # 3. 识别年份
        year = self._match_year(sentence)

        # 4. 识别数值+单位
        value, unit = self._match_value(sentence)

        if value is None:
            return None

        # 5. 推测声称的数据来源
        source = self._guess_source(sentence)

        return FinancialClaim(
            raw_text=sentence,
            entity=entity or "",
            metric=metric_raw,
            value=value,
            unit=unit,
            year=year,
            claim_type=claim_type,
            source=source,
        )

    def _match_metric(self, text: str) -> tuple[None, None] | tuple[str, ClaimType]:
        """匹配指标关键词。"""
        for keyword, (std_name, claim_type) in METRIC_MAP.items():
            if keyword in text:
                return std_name, claim_type
        return None, None

    def _match_company(self, text: str) -> str:
        """匹配公司名。"""
        m = COMPANY_PATTERN.search(text)
        if m:
            return m.group(1).strip()
        return ""

    def _match_year(self, text: str) -> Optional[int]:
        """匹配年份。"""
        m = YEAR_PATTERN.search(text)
        if m:
            return int(m.group(1))
        return None

    def _match_value(self, text: str) -> tuple[Optional[float], str]:
        """匹配数值和单位。"""
        m = NUMERIC_PATTERN.search(text)
        if m:
            return float(m.group(1)), m.group(2)
        return None, ""

    def _guess_source(self, text: str) -> str:
        """根据文本线索推测数据来源。"""
        if any(kw in text for kw in ("年报", "年度报告", "财报", "公告")):
            return "年报"
        if any(kw in text for kw in ("季报", "一季报", "三季报")):
            return "季报"
        if any(kw in text for kw in ("研报", "研究报", "券商")):
            return "研报"
        return ""


def normalize_to_yi(value: float, unit: str) -> float:
    """将数值统一换算到「亿元」。

    Examples:
        >>> normalize_to_yi(1.2, "万亿元")
        12000.0
        >>> normalize_to_yi(500, "万元")
        0.05
    """
    factor = UNIT_TO_YI.get(unit, 1)
    return value * factor
