# -*- coding: utf-8 -*-
"""
结果聚合器

将多个检测器的输出聚合为一个综合幻觉评分。
"""

from typing import List, Dict
from dataclasses import dataclass, field

from ..detectors.base import DetectorOutput, ClaimResult


@dataclass
class AggregatedResult:
    """聚合后的最终结果"""
    overall_score: float         # 0~1, 越高越可能有幻觉
    risk_level: str              # "low" / "medium" / "high"
    detector_scores: Dict[str, float] = field(default_factory=dict)
    flagged_claims: List[Dict] = field(default_factory=list)
    details: Dict = field(default_factory=dict)


class ResultAggregator:
    """
    多检测器结果聚合

    Parameters
    ----------
    weights : Dict[str, float], optional
        各检测器权重。默认全部等权。
        例: {"self_consistency": 0.4, "fact_check": 0.4, "confidence": 0.2}
    thresholds : Dict[str, float], optional
        风险等级阈值。默认: {"low": 0.3, "medium": 0.6, "high": 1.0}
    """

    def __init__(
        self,
        weights: Dict[str, float] = None,
        thresholds: Dict[str, float] = None,
    ):
        self.weights = weights or {}
        self.thresholds = thresholds or {
            "low": 0.3,
            "medium": 0.6,
            "high": 1.0,
        }

    def aggregate(
        self, outputs: List[DetectorOutput]
    ) -> AggregatedResult:
        if not outputs:
            return AggregatedResult(
                overall_score=0.0,
                risk_level="low",
                details={"reason": "无检测结果"},
            )

        # 收集各检测器分数
        detector_scores = {
            o.detector_name: o.overall_score for o in outputs
        }

        # 加权平均
        total_weight = 0.0
        weighted_sum = 0.0
        for name, score in detector_scores.items():
            w = self.weights.get(name, 1.0)
            weighted_sum += score * w
            total_weight += w

        overall = (
            weighted_sum / total_weight if total_weight > 0 else 0.0
        )

        # 风险等级
        if overall >= self.thresholds["medium"]:
            risk = "high"
        elif overall >= self.thresholds["low"]:
            risk = "medium"
        else:
            risk = "low"

        # 收集被标记的 claim
        flagged = []
        all_claims = set()
        for o in outputs:
            for cr in o.claim_results:
                all_claims.add(cr.claim)

        for claim_text in all_claims:
            claim_scores = {}
            claim_details = {}
            for o in outputs:
                for cr in o.claim_results:
                    if cr.claim == claim_text:
                        claim_scores[o.detector_name] = cr.score
                        claim_details[o.detector_name] = cr.detail
                        break

            avg_score = (
                sum(claim_scores.values()) / len(claim_scores)
                if claim_scores
                else 0
            )

            if avg_score > self.thresholds["low"]:
                flagged.append(
                    {
                        "claim": claim_text,
                        "score": round(avg_score, 4),
                        "detector_scores": {
                            k: round(v, 4)
                            for k, v in claim_scores.items()
                        },
                        "details": claim_details,
                    }
                )

        flagged.sort(key=lambda x: x["score"], reverse=True)

        return AggregatedResult(
            overall_score=round(overall, 4),
            risk_level=risk,
            detector_scores={
                k: round(v, 4) for k, v in detector_scores.items()
            },
            flagged_claims=flagged,
            details={
                "num_detectors": len(outputs),
                "num_claims_total": len(all_claims),
                "num_claims_flagged": len(flagged),
            },
        )
