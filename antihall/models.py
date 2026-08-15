"""核心数据模型 — 所有模块共享的数据结构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ClaimType(str, Enum):
    """声明类型"""
    REVENUE = "revenue"            # 营收
    NET_PROFIT = "net_profit"      # 净利润
    GROSS_MARGIN = "gross_margin"  # 毛利率
    GROWTH_RATE = "growth_rate"    # 增长率
    RATIO = "ratio"                # 其他比率
    ABSOLUTE = "absolute"          # 绝对数值
    DATE = "date"                  # 日期
    ENTITY = "entity"              # 实体名
    OTHER = "other"                # 其他


class Verdict(str, Enum):
    """核查结论"""
    CORRECT = "correct"        # 与真实数据一致
    HALLUCINATED = "hallucinated"  # 与真实数据不符
    UNVERIFIABLE = "unverifiable"  # 无法验证（数据源无数据）
    ERROR = "error"            # 检测过程出错


@dataclass
class FinancialClaim:
    """从文本中提取的一个金融声明。

    Examples:
        >>> # 文本: "贵州茅台2023年营收1505.6亿元"
        >>> claim = FinancialClaim(
        ...     raw_text="贵州茅台2023年营收1505.6亿元",
        ...     entity="贵州茅台",
        ...     metric="营收",
        ...     value=1505.6,
        ...     unit="亿元",
        ...     year=2023,
        ...     claim_type=ClaimType.REVENUE,
        ...     source="2023年报"  # 声称的数据来源
        ... )
    """
    raw_text: str                          # 原文片段
    entity: str                            # 实体名（公司名）
    metric: str                            # 指标名（营收/净利润/毛利率...）
    value: Optional[float] = None          # 声称的数值
    unit: str = ""                         # 单位（亿元/万元/%...）
    year: Optional[int] = None             # 年份
    quarter: Optional[int] = None          # 季度 (1-4)
    claim_type: ClaimType = ClaimType.OTHER
    source: str = ""                       # 声称的数据来源（如有）

    def __post_init__(self):
        """规整化：metric 统一小写无空格。"""
        if self.metric:
            self.metric = self.metric.strip()


@dataclass
class Evidence:
    """核查证据 — 来自真实数据源。"""
    source_name: str                       # 数据源名称（如 "AKShare-年报"）
    entity: str                            # 实际查询的实体
    metric: str                            # 指标
    actual_value: Optional[float] = None   # 真实数值
    unit: str = ""                         # 真实数值单位
    year: Optional[int] = None             # 真实数据年份
    url: str = ""                          # 可点击的证据链接
    raw_data: dict = field(default_factory=dict)  # 原始返回数据


@dataclass
class ClaimReport:
    """单条声明的完整核查报告。"""
    claim: FinancialClaim                  # 原始声明
    evidence: Optional[Evidence] = None    # 核查证据
    verdict: Verdict = Verdict.UNVERIFIABLE
    deviation: Optional[float] = None      # 偏差百分比 (声称值 - 真实值) / 真实值
    explanation: str = ""                  # 人话解释：为什么有问题
    suggestion: str = ""                   # 修改建议：应该怎么改


@dataclass
class CheckResult:
    """整段文本的核查结果。"""
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
        """幻觉率 = 幻觉数 / 已验证声明数。"""
        verified = self.correct_count + self.hallucinated_count
        if verified == 0:
            return 0.0
        return self.hallucinated_count / verified

    @property
    def risk_level(self) -> str:
        """风险等级。"""
        rate = self.hallucination_rate
        if rate >= 0.5:
            return "高风险"
        elif rate >= 0.2:
            return "中风险"
        elif rate > 0:
            return "低风险"
        return "无风险"

    def summary(self) -> str:
        """一句话摘要。"""
        return (
            f"共检测 {self.total_claims} 条声明，"
            f"其中 {self.hallucinated_count} 条幻觉、"
            f"{self.correct_count} 条正确、"
            f"{self.unverifiable_count} 条无法验证。"
            f"幻觉率 {self.hallucination_rate:.0%}，风险等级：{self.risk_level}。"
        )
