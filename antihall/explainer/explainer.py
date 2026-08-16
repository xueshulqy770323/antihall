# -*- coding: utf-8 -*-
"""Explainer - generates human-readable explanations for both numeric and semantic claims.

For each claim report, fills in:
1. explanation: what's wrong and why
2. suggestion: how to fix it (with correct values)
3. evidence URL is carried in the Evidence object
"""
from __future__ import annotations

from antihall.models import (
    ClaimReport,
    Evidence,
    FinancialClaim,
    SemanticClaim,
    SemanticType,
    Verdict,
)
from antihall.extractor.claim_extractor import normalize_to_yi


class Explainer:
    """Generate human-readable explanations and correction suggestions."""

    def explain(self, report: ClaimReport) -> ClaimReport:
        """Fill in explanation and suggestion for a report."""
        claim = report.claim
        evidence = report.evidence

        # If explanation is already set (e.g. by semantic verifier), keep it
        if report.explanation:
            return report

        if isinstance(claim, SemanticClaim):
            return self._explain_semantic(report)

        # Numeric claim explanations
        if report.verdict == Verdict.CORRECT:
            report.explanation = self._explain_correct(claim, evidence)
        elif report.verdict == Verdict.HALLUCINATED:
            report.explanation = self._explain_hallucinated(claim, evidence, report.deviation)
            report.suggestion = self._suggest_correction(claim, evidence)
        elif report.verdict == Verdict.UNVERIFIABLE:
            report.explanation = self._explain_unverifiable(claim)
        elif report.verdict == Verdict.ERROR:
            report.explanation = "\u8be5\u58f0\u660e\u65e0\u6cd5\u89e3\u6790\u51fa\u53ef\u9a8c\u8bc1\u7684\u6570\u503c\u3002"

        return report

    # ------------------------------------------------------------------- #
    # Numeric claim explanations
    # ------------------------------------------------------------------- #

    def _explain_correct(self, claim: FinancialClaim, ev: Evidence) -> str:
        return (
            f"\u6838\u67e5\u901a\u8fc7\u3002{claim.entity}{claim.year}\u5e74{claim.metric}"
            f"\u4e3a{ev.actual_value}{ev.unit}\uff08\u6570\u636e\u6e90\uff1a{ev.source_name}\uff09\uff0c"
            f"\u6587\u672c\u4e2d\u5199\u7684\u662f{claim.value}{claim.unit}\uff0c\u6570\u503c\u4e00\u81f4\u3002"
        )

    def _explain_hallucinated(
        self,
        claim: FinancialClaim,
        ev: Evidence,
        deviation: float,
    ) -> str:
        if claim.metric in ("\u6bdb\u5229\u7387", "\u51c0\u5229\u7387", "\u8d44\u4ea7\u8d1f\u503a\u7387", "ROE",
                            "\u540c\u6bd4\u589e\u957f\u7387", "\u540c\u6bd4\u589e\u51cf\u7387"):
            diff_desc = f"\u504f\u5dee{abs(deviation):.1f}\u4e2a\u767e\u5206\u70b9"
        else:
            diff_desc = f"\u504f\u5dee{abs(deviation):.1%}"

        direction = "\u9ad8" if deviation > 0 else "\u4f4e"

        return (
            f"\u6570\u5b57\u5e7b\u89c9\u3002\u6587\u672c\u79f0{claim.entity}{claim.year}\u5e74{claim.metric}"
            f"\u4e3a{claim.value}{claim.unit}\uff0c\u4f46{ev.source_name}\u6570\u636e\u663e\u793a"
            f"\u5b9e\u9645\u503c\u4e3a{ev.actual_value}{ev.unit}\uff0c"
            f"\u6587\u672c\u6bd4\u771f\u5b9e\u503c{direction}{diff_desc}\u3002"
        )

    def _explain_unverifiable(self, claim: FinancialClaim) -> str:
        reasons = []
        if not claim.entity:
            reasons.append("\u672a\u8bc6\u522b\u5230\u516c\u53f8\u540d")
        if claim.year is None:
            reasons.append("\u672a\u8bc6\u522b\u5230\u5e74\u4efd")
        if not reasons:
            reasons.append("\u6570\u636e\u6e90\u4e2d\u672a\u627e\u5230\u8be5\u516c\u53f8\u8be5\u5e74\u4efd\u7684\u8d22\u62a5\u6570\u636e")

        return (
            f"\u65e0\u6cd5\u9a8c\u8bc1\u3002\u539f\u56e0\uff1a{'\u3001'.join(reasons)}\u3002"
            f"\u5efa\u8bae\u4eba\u5de5\u6838\u67e5{claim.entity or '\u8be5\u516c\u53f8'}"
            f"{claim.year or '\u5bf9\u5e94\u5e74\u4efd'}\u7684{claim.metric}\u6570\u636e\u3002"
        )

    def _suggest_correction(self, claim: FinancialClaim, ev: Evidence) -> str:
        return (
            f"\u5efa\u8bae\u4fee\u6539\u4e3a\uff1a{claim.entity}{claim.year}\u5e74{claim.metric}"
            f"\u4e3a{ev.actual_value}{ev.unit}\u3002"
            f"\u8bc1\u636e\u6765\u6e90\uff1a{ev.url}"
        )

    # ------------------------------------------------------------------- #
    # Semantic claim explanations (fallback if verifier didn't set them)
    # ------------------------------------------------------------------- #

    def _explain_semantic(self, report: ClaimReport) -> ClaimReport:
        """Generate fallback explanation for semantic claims if not already set."""
        claim = report.claim  # SemanticClaim

        if report.verdict == Verdict.UNVERIFIABLE and not report.explanation:
            report.explanation = (
                f"\u65e0\u6cd5\u9a8c\u8bc1\u8be5\u8bed\u4e49\u58f0\u660e\u3002"
                f"\u5efa\u8bae\u4eba\u5de5\u6838\u67e5\uff1a\u201c{claim.raw_text}\u201d"
            )

        # Add evidence link to suggestion if available
        if report.evidence and report.evidence.url and not report.suggestion:
            report.suggestion = f"\u8bc1\u636e\u6765\u6e90\uff1a{report.evidence.url}"

        return report


# ----------------------------------------------------------------------- #
# Global singleton
# ----------------------------------------------------------------------- #
_default_explainer = Explainer()


def explain_report(report: ClaimReport) -> ClaimReport:
    """Convenience function: explain a single report."""
    return _default_explainer.explain(report)
