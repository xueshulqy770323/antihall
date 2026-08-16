# -*- coding: utf-8 -*-
"""Detection pipeline — orchestrates the full hallucination detection flow.

The pipeline coordinates four stages:

1. Extraction:   text -> [FinancialClaim | SemanticClaim]
                 - Regex extractor (always available, no API key needed)
                 - LLM extractor (optional, requires API key)
                 - Merge results, deduplicate

2. Data fetch:   each claim -> Evidence (real financial data from AKShare)

3. Verification: claim + evidence -> verdict
                 - Numeric claims  -> NumericVerifier
                 - Semantic claims -> SemanticVerifier

4. Explanation:  verdict -> human-readable explanation + suggestion + evidence URL
"""
from __future__ import annotations

import logging
from typing import Optional

from antihall.models import (
    AnyClaim,
    CheckResult,
    ClaimReport,
    Evidence,
    FinancialClaim,
    SemanticClaim,
)
from antihall.extractor.claim_extractor import ClaimExtractor
from antihall.extractor.llm_extractor import LLMClaimExtractor
from antihall.datasource.akshare_source import AKShareDataSource
from antihall.verifier.numeric_verifier import NumericVerifier
from antihall.verifier.semantic_verifier import SemanticVerifier
from antihall.explainer.explainer import Explainer
from antihall.llm.client import LLMClient, LLMConfig

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """Orchestrates the full detection flow.

    Attributes:
        regex_extractor: Always-on regex-based extractor (no API key needed)
        llm_extractor: Optional LLM-based extractor (needs API key)
        datasource: AKShare data source for real financial data
        numeric_verifier: Verifies numeric claims
        semantic_verifier: Verifies semantic claims
        explainer: Generates human-readable explanations
    """

    def __init__(
        self,
        datasource: Optional[AKShareDataSource] = None,
        llm_client: Optional[LLMClient] = None,
        use_llm: bool = True,
    ):
        self.datasource = datasource or AKShareDataSource()
        self.llm_client = llm_client
        self.regex_extractor = ClaimExtractor()
        self.llm_extractor = (
            LLMClaimExtractor(llm_client)
            if (use_llm and llm_client and llm_client.is_available)
            else None
        )
        self.numeric_verifier = NumericVerifier()
        self.semantic_verifier = SemanticVerifier(
            datasource=self.datasource,
            llm_client=llm_client,
        )
        self.explainer = Explainer()

    def run(self, text: str) -> CheckResult:
        """Run the full pipeline on input text.

        Args:
            text: Chinese financial text to check.

        Returns:
            CheckResult with all claims verified and explained.
        """
        result = CheckResult(input_text=text)

        # ── Stage 1: Extraction ──
        all_claims = self._extract_claims(text)
        logger.info(f"Extracted {len(all_claims)} claims total")

        # ── Stage 2 & 3: Fetch data + Verify ──
        for claim in all_claims:
            report = self._verify_claim(claim)
            result.claims.append(report)

        # ── Stage 4: Explanation ──
        for i, report in enumerate(result.claims):
            result.claims[i] = self.explainer.explain(report)

        return result

    # ------------------------------------------------------------------- #
    # Stage 1: Extraction
    # ------------------------------------------------------------------- #

    def _extract_claims(self, text: str) -> list[AnyClaim]:
        """Extract claims from text using regex + optional LLM.

        Strategy:
        1. Always run regex extractor (fast, free, no dependencies)
        2. If LLM is available, also run LLM extractor
        3. Merge results: LLM claims supplement regex claims
        4. Deduplicate by (entity, metric, value, year)
        """
        # Regex extraction (always)
        regex_claims = self.regex_extractor.extract(text)
        logger.info(f"Regex extractor found {len(regex_claims)} numeric claims")

        if not self.llm_extractor:
            # LLM not available — just use regex results
            return list(regex_claims)

        # LLM extraction (optional)
        try:
            llm_claims = self.llm_extractor.extract(text)
            logger.info(f"LLM extractor found {len(llm_claims)} claims")
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return list(regex_claims)

        # Merge: start with regex numeric claims, add LLM numeric + semantic
        merged: list[AnyClaim] = list(regex_claims)

        for llm_claim in llm_claims:
            if isinstance(llm_claim, SemanticClaim):
                # Always add semantic claims (regex can't produce these)
                merged.append(llm_claim)
            elif isinstance(llm_claim, FinancialClaim):
                # Deduplicate against regex claims
                if not self._is_duplicate(llm_claim, merged):
                    merged.append(llm_claim)

        return merged

    @staticmethod
    def _is_duplicate(claim: FinancialClaim, existing: list[AnyClaim]) -> bool:
        """Check if a numeric claim is already covered by existing claims."""
        for existing_claim in existing:
            if not isinstance(existing_claim, FinancialClaim):
                continue
            if (
                existing_claim.entity == claim.entity
                and existing_claim.metric == claim.metric
                and existing_claim.year == claim.year
                and claim.value is not None
                and existing_claim.value is not None
                and abs(existing_claim.value - claim.value) < 0.1
            ):
                return True
        return False

    # ------------------------------------------------------------------- #
    # Stage 2 & 3: Fetch data + Verify
    # ------------------------------------------------------------------- #

    def _verify_claim(self, claim: AnyClaim) -> ClaimReport:
        """Fetch evidence and verify a single claim."""
        if isinstance(claim, FinancialClaim):
            return self._verify_numeric(claim)
        elif isinstance(claim, SemanticClaim):
            return self._verify_semantic(claim)
        else:
            return ClaimReport(
                claim=claim,
                verdict=__import__(
                    "antihall.models", fromlist=["Verdict"]
                ).Verdict.ERROR,
                explanation="Unknown claim type",
            )

    def _verify_numeric(self, claim: FinancialClaim) -> ClaimReport:
        """Verify a numeric claim: fetch evidence + compare."""
        evidence = None
        if claim.entity and claim.metric:
            evidence = self.datasource.get_evidence(
                entity=claim.entity,
                metric=claim.metric,
                year=claim.year,
            )
        return self.numeric_verifier.verify(claim, evidence)

    def _verify_semantic(self, claim: SemanticClaim) -> ClaimReport:
        """Verify a semantic claim: fetch evidence + check logic."""
        return self.semantic_verifier.verify(claim)
