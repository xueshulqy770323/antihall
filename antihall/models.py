# -*- coding: utf-8 -*-
"""Core data models shared across all antihall modules.

v3.0: adds semantic claim types (causal, trend, temporal, metric-confusion)
and a unified SemanticClaim hierarchy alongside the original FinancialClaim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class ClaimType(str, Enum):
    """Numeric claim types (original)."""
    REVENUE = "revenue"
    NET_PROFIT = "net_profit"
    GROSS_MARGIN = "gross_margin"
    GROWTH_RATE = "growth_rate"
    RATIO = "ratio"
    ABSOLUTE = "absolute"
    DATE = "date"
    ENTITY = "entity"
    OTHER = "other"


class SemanticType(str, Enum):
    """Semantic hallucination types (v3.0).

    These go beyond numeric comparison — they detect meaning-level
    fabrications that a simple number check cannot catch.
    """
    CAUSAL = "causal"                    # 因果编造: 把不存在的因果关系说成事实
    TREND_REVERSAL = "trend_reversal"    # 趋势颠倒: 下降说成增长
    TEMPORAL_MISMATCH = "temporal_mismatch"  # 时间错位: 2022数据说成2023
    METRIC_CONFUSION = "metric_confusion"    # 指标混淆: 营收说成利润


class Verdict(str, Enum):
    """Verification verdict."""
    CORRECT = "correct"
    HALLUCINATED = "hallucinated"
    UNVERIFIABLE = "unverifiable"
    ERROR = "error"


class ExtractorMode(str, Enum):
    """Which extractor was used."""
    REGEX = "regex"
    LLM = "llm"


# --------------------------------------------------------------------------- #
# Claim models
# --------------------------------------------------------------------------- #

@dataclass
class FinancialClaim:
    """A numeric financial claim extracted from text."""
    raw_text: str
    entity: str
    metric: str
    value: Optional[float] = None
    unit: str = ""
    year: Optional[int] = None
    quarter: Optional[int] = None
    claim_type: ClaimType = ClaimType.OTHER
    source: str = ""
    extractor: ExtractorMode = ExtractorMode.REGEX

    def __post_init__(self):
        if self.metric:
            self.metric = self.metric.strip()


@dataclass
class SemanticClaim:
    """A semantic financial claim that needs LLM + data verification.

    Unlike FinancialClaim (pure number), SemanticClaim captures
    meaning-level assertions that can be wrong even if the number is right.

    Examples:
        Causal: "因原材料降价，毛利率提升" — 原材料可能其实是涨的
        Trend:  "连续三年增长" — 可能其实是下降的
        Temporal: "2023年营收1500亿" — 1500亿可能是2022年的
        Metric: "净利润1500亿" — 1500亿可能是营收不是利润
    """
    raw_text: str
    entity: str
    semantic_type: SemanticType
    claim_text: str                     # normalized claim sentence
    claimed_cause: str = ""             # 因果类: 声称的原因
    claimed_effect: str = ""            # 因果类: 声称的结果
    claimed_direction: str = ""         # 趋势类: "上升"/"下降"/"增长"/"下滑"
    claimed_period: str = ""            # 趋势类: "连续三年"/"2021-2023"
    claimed_year: Optional[int] = None  # 时间类: 声称的年份
    actual_year_data: Optional[int] = None  # 时间类: 数字实际对应的年份
    claimed_metric: str = ""            # 指标混淆: 声称的指标
    actual_metric: str = ""             # 指标混淆: 实际对应的指标
    year: Optional[int] = None
    extractor: ExtractorMode = ExtractorMode.LLM


# Union type for pipeline
AnyClaim = Union[FinancialClaim, SemanticClaim]


# --------------------------------------------------------------------------- #
# Evidence & Report
# --------------------------------------------------------------------------- #

@dataclass
class Evidence:
    """Verification evidence from real data sources."""
    source_name: str
    entity: str
    metric: str
    actual_value: Optional[float] = None
    unit: str = ""
    year: Optional[int] = None
    url: str = ""
    raw_data: dict = field(default_factory=dict)
    # v3: support multi-year trend data
    trend_data: list[dict] = field(default_factory=list)  # [{"year": 2021, "value": 100}, ...]


@dataclass
class ClaimReport:
    """Complete verification report for a single claim.

    Works for both numeric (FinancialClaim) and semantic (SemanticClaim).
    """
    claim: Union[FinancialClaim, SemanticClaim]
    evidence: Optional[Evidence] = None
    verdict: Verdict = Verdict.UNVERIFIABLE
    deviation: Optional[float] = None
    explanation: str = ""
    suggestion: str = ""
    # v3: semantic-specific fields
    semantic_type: Optional[SemanticType] = None


@dataclass
class CheckResult:
    """Verification result for an entire text passage."""
    input_text: str
    claims: list[ClaimReport] = field(default_factory=list)

    @property
    def total_claims(self) -> int:
        return len(self.claims)

    @property
    def hallucinated_count(self) -> int:
        return sum(1 for c in self.claims if c.verdict == Verdict.HALLUCINATED)

    @property
    def correct_count(self) -> int:
        return sum(1 for c in self.claims if c.verdict == Verdict.CORRECT)

    @property
    def unverifiable_count(self) -> int:
        return sum(1 for c in self.claims if c.verdict == Verdict.UNVERIFIABLE)

    @property
    def hallucination_rate(self) -> float:
        verified = self.correct_count + self.hallucinated_count
        if verified == 0:
            return 0.0
        return self.hallucinated_count / verified

    @property
    def risk_level(self) -> str:
        rate = self.hallucination_rate
        if rate >= 0.5:
            return "\u9ad8\u98ce\u9669"  # 高风险
        elif rate >= 0.2:
            return "\u4e2d\u98ce\u9669"  # 中风险
        elif rate > 0:
            return "\u4f4e\u98ce\u9669"  # 低风险
        return "\u65e0\u98ce\u9669"      # 无风险

    def summary(self) -> str:
        return (
            f"\u5171\u68c0\u6d4b {self.total_claims} \u6761\u58f0\u660e\uff0c"  # 共检测 N 条声明，
            f"\u5176\u4e2d {self.hallucinated_count} \u6761\u5e7b\u89c9\u3001"  # 其中 N 条幻觉、
            f"{self.correct_count} \u6761\u6b63\u786e\u3001"                    # N 条正确、
            f"{self.unverifiable_count} \u6761\u65e0\u6cd5\u9a8c\u8bc1\u3002"  # N 条无法验证。
            f"\u5e7b\u89c9\u7387 {self.hallucination_rate:.0%}\uff0c"          # 幻觉率 N%，
            f"\u98ce\u9669\u7b49\u7ea7\uff1a{self.risk_level}\u3002"            # 风险等级：X。
        )
