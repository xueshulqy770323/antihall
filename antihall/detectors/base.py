# -*- coding: utf-8 -*-
"""
检测器基类
"""

from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass, field


@dataclass
class ClaimResult:
    """单条声明的检测结果"""
    claim: str
    score: float           # 0~1, 越高越可能是幻觉
    detail: str = ""        # 检测细节说明
    evidence: dict = field(default_factory=dict)


@dataclass
class DetectorOutput:
    """单个检测器的完整输出"""
    detector_name: str
    overall_score: float    # 0~1, 越高越可能含幻觉
    claim_results: List[ClaimResult] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


class BaseDetector(ABC):
    """所有检测器的抽象基类"""

    name: str = "base"

    @abstractmethod
    def detect(self, text: str, claims: List[str] = None) -> DetectorOutput:
        """
        检测文本中的幻觉

        Parameters
        ----------
        text : str
            待检测的完整文本
        claims : List[str], optional
            预先拆分好的声明列表。如不提供，检测器自行拆分。

        Returns
        -------
        DetectorOutput
        """
        ...
