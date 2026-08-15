# -*- coding: utf-8 -*-
"""
antihall 核心入口

HallucinationDetector 是用户面对的主接口，内部编排多个子检测器。
"""

from typing import List, Optional, Dict
from dataclasses import dataclass, field

from .detectors.base import BaseDetector, DetectorOutput, ClaimResult
from .detectors.self_consistency import SelfConsistencyDetector
from .detectors.confidence import ConfidenceDetector
from .detectors.fact_check import FactCheckDetector
from .verifiers.aggregator import ResultAggregator, AggregatedResult
from .utils.llm_client import LLMClient
from .utils.text import split_claims


@dataclass
class DetectionResult:
    """
    幻觉检测最终结果

    用户通过 HallucinationDetector.check() 获得此对象。
    """
    overall_score: float                            # 0~1, 越高越可能含幻觉
    risk_level: str                                 # "low" / "medium" / "high"
    flagged_claims: List[Dict] = field(default_factory=list)
    detector_outputs: List[DetectorOutput] = field(default_factory=list)
    aggregated: Optional[AggregatedResult] = None

    def __str__(self) -> str:
        lines = [
            f"幻觉检测报告",
            f"{'='*40}",
            f"综合评分: {self.overall_score:.2%}",
            f"风险等级: {self.risk_level}",
            f"被标记声明数: {len(self.flagged_claims)}",
        ]
        if self.flagged_claims:
            lines.append(f"\n高风险声明:")
            for i, fc in enumerate(self.flagged_claims, 1):
                lines.append(f"  {i}. [{fc['score']:.2%}] {fc['claim']}")
                for det, detail in fc.get("details", {}).items():
                    lines.append(f"     - {det}: {detail}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """转为字典 (便于 JSON 序列化)"""
        import dataclasses

        return {
            "overall_score": self.overall_score,
            "risk_level": self.risk_level,
            "flagged_claims": self.flagged_claims,
            "detector_outputs": [
                {
                    "detector_name": o.detector_name,
                    "overall_score": o.overall_score,
                    "claim_results": [
                        dataclasses.asdict(cr) for cr in o.claim_results
                    ],
                    "meta": o.meta,
                }
                for o in self.detector_outputs
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """转为 JSON 字符串"""
        import json
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class HallucinationDetector:
    """
    AI 幻觉检测器 - 主接口

    将多个子检测器组合使用，给出综合幻觉评估。

    Parameters
    ----------
    api_key : str, optional
        LLM API 密钥 (OpenAI/Anthropic)。也可通过环境变量设置。
    provider : str
        LLM 提供商: "openai" / "anthropic" / "custom"
    model : str
        模型名称
    detectors : List[str], optional
        启用的检测器列表。默认全部启用:
        ["self_consistency", "confidence", "fact_check"]
    weights : Dict[str, float], optional
        各检测器在综合评分中的权重
    llm_client : LLMClient, optional
        自定义 LLM 客户端 (覆盖 api_key/provider/model 的自动创建)
    **llm_kwargs
        传递给 LLMClient 的额外参数 (如 temperature, max_tokens, base_url)

    Examples
    --------
    >>> from antihall import HallucinationDetector
    >>>
    >>> detector = HallucinationDetector(api_key="sk-xxx")
    >>> result = detector.check("巴黎是法国的首都，面积约为105平方公里。")
    >>> print(result)
    """

    DEFAULT_WEIGHTS = {
        "self_consistency": 0.4,
        "fact_check": 0.4,
        "confidence": 0.2,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        detectors: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        llm_client: Optional[LLMClient] = None,
        **llm_kwargs,
    ):
        # 初始化 LLM 客户端
        if llm_client is not None:
            self.llm = llm_client
        else:
            self.llm = LLMClient(
                api_key=api_key,
                provider=provider,
                model=model,
                **llm_kwargs,
            )

        # 选择检测器
        detector_names = detectors or [
            "self_consistency",
            "confidence",
            "fact_check",
        ]

        self.detectors: List[BaseDetector] = []
        for name in detector_names:
            if name == "self_consistency":
                self.detectors.append(
                    SelfConsistencyDetector(self.llm)
                )
            elif name == "confidence":
                self.detectors.append(
                    ConfidenceDetector(self.llm)
                )
            elif name == "fact_check":
                self.detectors.append(
                    FactCheckDetector(self.llm)
                )
            else:
                raise ValueError(
                    f"未知检测器: {name}。"
                    f"可选: self_consistency, confidence, fact_check"
                )

        # 初始化聚合器
        self.aggregator = ResultAggregator(
            weights=weights or self.DEFAULT_WEIGHTS
        )

    def check(
        self,
        text: str,
        claims: Optional[List[str]] = None,
        return_details: bool = True,
    ) -> DetectionResult:
        """
        检测文本中的幻觉

        Parameters
        ----------
        text : str
            待检测文本
        claims : List[str], optional
            预先拆分好的声明列表
        return_details : bool
            是否在结果中保留各检测器详细输出

        Returns
        -------
        DetectionResult
        """
        if claims is None:
            claims = split_claims(text)

        # 运行各检测器
        outputs: List[DetectorOutput] = []
        for detector in self.detectors:
            output = detector.detect(text, claims=claims)
            outputs.append(output)

        # 聚合
        aggregated = self.aggregator.aggregate(outputs)

        return DetectionResult(
            overall_score=aggregated.overall_score,
            risk_level=aggregated.risk_level,
            flagged_claims=aggregated.flagged_claims,
            detector_outputs=outputs if return_details else [],
            aggregated=aggregated,
        )

    def check_batch(
        self, texts: List[str], **kwargs
    ) -> List[DetectionResult]:
        """
        批量检测

        Parameters
        ----------
        texts : List[str]
            待检测文本列表

        Returns
        -------
        List[DetectionResult]
        """
        return [self.check(t, **kwargs) for t in texts]
