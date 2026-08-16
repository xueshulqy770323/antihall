# -*- coding: utf-8 -*-
"""antihall - Chinese financial report hallucination detection toolkit.

v3.0: adds LLM-powered semantic detection (causal, trend, temporal, metric confusion)
on top of the original numeric verification pipeline.
"""

from antihall.core import HallucinationChecker, CheckResult, ClaimReport
from antihall.models import (
    FinancialClaim,
    SemanticClaim,
    SemanticType,
    ClaimType,
    Verdict,
)
from antihall.llm.client import LLMClient, LLMConfig

__version__ = "3.0.0"
__all__ = [
    "HallucinationChecker",
    "CheckResult",
    "ClaimReport",
    "FinancialClaim",
    "SemanticClaim",
    "SemanticType",
    "ClaimType",
    "Verdict",
    "LLMClient",
    "LLMConfig",
]
