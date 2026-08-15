# -*- coding: utf-8 -*-
"""Tests for the aggregator"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from antihall.detectors.base import DetectorOutput, ClaimResult
from antihall.verifiers.aggregator import ResultAggregator


def test_aggregator_basic():
    outputs = [
        DetectorOutput(
            detector_name="self_consistency",
            overall_score=0.6,
            claim_results=[
                ClaimResult(claim="claim A", score=0.7, detail="low support"),
                ClaimResult(claim="claim B", score=0.2, detail="ok"),
            ],
        ),
        DetectorOutput(
            detector_name="fact_check",
            overall_score=0.4,
            claim_results=[
                ClaimResult(claim="claim A", score=0.8, detail="not found"),
                ClaimResult(claim="claim B", score=0.1, detail="verified"),
            ],
        ),
    ]

    agg = ResultAggregator()
    result = agg.aggregate(outputs)

    # Weighted: (0.6*1 + 0.4*1) / 2 = 0.5
    assert 0.4 <= result.overall_score <= 0.6
    assert result.risk_level == "medium"

    # claim A should be flagged (avg: (0.7+0.8)/2 = 0.75 > 0.3)
    assert len(result.flagged_claims) >= 1
    assert result.flagged_claims[0]["claim"] == "claim A"


def test_aggregator_empty():
    agg = ResultAggregator()
    result = agg.aggregate([])
    assert result.overall_score == 0.0
    assert result.risk_level == "low"


def test_aggregator_custom_weights():
    outputs = [
        DetectorOutput(
            detector_name="self_consistency",
            overall_score=0.8,
            claim_results=[],
        ),
        DetectorOutput(
            detector_name="fact_check",
            overall_score=0.2,
            claim_results=[],
        ),
    ]

    agg = ResultAggregator(weights={"self_consistency": 3, "fact_check": 1})
    result = agg.aggregate(outputs)

    # Weighted: (0.8*3 + 0.2*1) / 4 = 0.65
    assert abs(result.overall_score - 0.65) < 0.01


if __name__ == "__main__":
    test_aggregator_basic()
    test_aggregator_empty()
    test_aggregator_custom_weights()
    print("All aggregator tests passed!")
