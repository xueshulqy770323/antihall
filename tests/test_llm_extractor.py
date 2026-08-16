# -*- coding: utf-8 -*-
"""Test the LLM claim extractor with a mock LLM client."""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from antihall.llm.client import LLMClient, LLMConfig
from antihall.extractor.llm_extractor import LLMClaimExtractor
from antihall.models import FinancialClaim, SemanticClaim, SemanticType, ClaimType, ExtractorMode


class MockLLMClient(LLMClient):
    """Mock LLM client that returns predefined JSON responses."""

    def __init__(self, mock_response):
        # Don't call super().__init__ to avoid SDK init
        self.config = LLMConfig(api_key="mock-key")
        self._client = None
        self._mock_response = mock_response

    def chat_json(self, prompt: str, system: str = "") -> list | dict:
        return self._mock_response

    @property
    def is_available(self) -> bool:
        return True


def test_extract_numeric_from_llm():
    """Test LLM extraction of a numeric claim."""
    mock_response = [
        {
            "type": "numeric",
            "raw_text": "\u8d35\u5dde\u8305\u53f0 2023 \u5e74\u8425\u6536 1505.6 \u4ebf\u5143",
            "entity": "\u8d35\u5dde\u8305\u53f0",
            "metric": "\u8425\u6536",
            "value": 1505.6,
            "unit": "\u4ebf\u5143",
            "year": 2023,
        }
    ]
    client = MockLLMClient(mock_response)
    extractor = LLMClaimExtractor(client)

    claims = extractor.extract("\u8d35\u5dde\u8305\u53f0 2023 \u5e74\u8425\u6536 1505.6 \u4ebf\u5143\u3002")

    assert len(claims) == 1
    c = claims[0]
    assert isinstance(c, FinancialClaim)
    assert c.entity == "\u8d35\u5dde\u8305\u53f0"
    assert c.metric == "\u8425\u6536"
    assert c.value == 1505.6
    assert c.unit == "\u4ebf\u5143"
    assert c.year == 2023
    assert c.claim_type == ClaimType.REVENUE
    assert c.extractor == ExtractorMode.LLM


def test_extract_semantic_causal():
    """Test LLM extraction of a causal semantic claim."""
    mock_response = [
        {
            "type": "semantic",
            "raw_text": "\u56e0\u539f\u6750\u6599\u964d\u4ef7\uff0c\u6bdb\u5229\u7387\u63d0\u5347",
            "entity": "\u8d35\u5dde\u8305\u53f0",
            "semantic_type": "causal",
            "claim_text": "\u539f\u6750\u6599\u964d\u4ef7\u5bfc\u81f4\u6bdb\u5229\u7387\u63d0\u5347",
            "detail": {
                "cause": "\u539f\u6750\u6599\u964d\u4ef7",
                "effect": "\u6bdb\u5229\u7387\u63d0\u5347",
            },
        }
    ]
    client = MockLLMClient(mock_response)
    extractor = LLMClaimExtractor(client)

    claims = extractor.extract("\u56e0\u539f\u6750\u6599\u964d\u4ef7\uff0c\u8305\u53f0\u6bdb\u5229\u7387\u63d0\u5347\u3002")

    assert len(claims) == 1
    c = claims[0]
    assert isinstance(c, SemanticClaim)
    assert c.semantic_type == SemanticType.CAUSAL
    assert c.claimed_cause == "\u539f\u6750\u6599\u964d\u4ef7"
    assert c.claimed_effect == "\u6bdb\u5229\u7387\u63d0\u5347"


def test_extract_semantic_trend():
    """Test LLM extraction of a trend reversal claim."""
    mock_response = [
        {
            "type": "semantic",
            "raw_text": "\u8425\u6536\u8fde\u7eed\u4e09\u5e74\u589e\u957f",
            "entity": "\u6bd4\u4e9a\u8fea",
            "semantic_type": "trend_reversal",
            "claim_text": "\u8425\u6536\u8fde\u7eed\u4e09\u5e74\u589e\u957f",
            "detail": {
                "direction": "\u589e\u957f",
                "period": "\u8fde\u7eed\u4e09\u5e74",
            },
        }
    ]
    client = MockLLMClient(mock_response)
    extractor = LLMClaimExtractor(client)

    claims = extractor.extract("\u6bd4\u4e9a\u8fea\u8425\u6536\u8fde\u7eed\u4e09\u5e74\u589e\u957f\u3002")

    assert len(claims) == 1
    c = claims[0]
    assert isinstance(c, SemanticClaim)
    assert c.semantic_type == SemanticType.TREND_REVERSAL
    assert c.claimed_direction == "\u589e\u957f"
    assert c.claimed_period == "\u8fde\u7eed\u4e09\u5e74"


def test_extract_empty_response():
    """Test LLM extraction with empty response."""
    client = MockLLMClient([])
    extractor = LLMClaimExtractor(client)

    claims = extractor.extract("\u4eca\u5929\u5929\u6c14\u4e0d\u9519\u3002")
    assert len(claims) == 0


def test_extract_no_llm_available():
    """Test that extraction returns empty list without LLM."""
    config = LLMConfig()  # no api_key
    client = LLMClient(config)
    extractor = LLMClaimExtractor(client)

    assert not extractor.is_available
    claims = extractor.extract("\u8d35\u5dde\u8305\u53f0 2023 \u5e74\u8425\u6536 1505.6 \u4ebf\u5143\u3002")
    assert len(claims) == 0


if __name__ == "__main__":
    test_extract_numeric_from_llm()
    test_extract_semantic_causal()
    test_extract_semantic_trend()
    test_extract_empty_response()
    test_extract_no_llm_available()
    print("All tests passed!")
