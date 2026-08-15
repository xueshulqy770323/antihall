# -*- coding: utf-8 -*-
"""
antihall - AI 幻觉检测工具库

一个用于检测和缓解大语言模型 (LLM) 幻觉的 Python 工具库。

核心检测器:
  - SelfConsistencyDetector: 自洽性检测 (基于 SelfCheckGPT 思路)
  - ConfidenceDetector: 基于 token logprob 的置信度评估
  - FactCheckDetector: 外部知识源事实核查

用法:
    from antihall import HallucinationDetector

    detector = HallucinationDetector(api_key="sk-...")
    result = detector.check("巴黎是法国的首都。")
    print(result.score, result.flagged_claims)
"""

from .core import HallucinationDetector, DetectionResult
from .detectors import (
    SelfConsistencyDetector,
    ConfidenceDetector,
    FactCheckDetector,
)

__version__ = "0.1.0"
__all__ = [
    "HallucinationDetector",
    "DetectionResult",
    "SelfConsistencyDetector",
    "ConfidenceDetector",
    "FactCheckDetector",
]
