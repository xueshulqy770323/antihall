# -*- coding: utf-8 -*-
"""
自洽性检测器 (Self-Consistency Detector)

核心思路 (参考 SelfCheckGPT, Manakul et al., 2023):
  1. 对同一问题让 LLM 采样 N 次回答 (高 temperature)
  2. 将原始回答按句拆分为 claim
  3. 对每个 claim，判断其他 N 个采样回答是否支持该 claim
  4. 如果多数采样回答不支持 → 该 claim 可能是幻觉

论文: "SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for
Generative Large Language Models" (EMNLP 2023)
https://arxiv.org/abs/2303.08896
"""

from typing import List, Optional
from dataclasses import dataclass

from .base import BaseDetector, DetectorOutput, ClaimResult
from ..utils.llm_client import LLMClient
from ..utils.text import split_claims


class SelfConsistencyDetector(BaseDetector):
    """
    自洽性检测器

    通过多次采样 + 交叉验证检测幻觉。

    Parameters
    ----------
    llm_client : LLMClient
        LLM 客户端实例
    num_samples : int
        采样次数 (默认 5)
    consistency_threshold : float
        一致性阈值。支持比例低于此值时判定为幻觉 (默认 0.5)
    """

    name = "self_consistency"

    def __init__(
        self,
        llm_client: LLMClient,
        num_samples: int = 5,
        consistency_threshold: float = 0.5,
    ):
        self.llm = llm_client
        self.num_samples = num_samples
        self.threshold = consistency_threshold

    def detect(
        self, text: str, claims: List[str] = None
    ) -> DetectorOutput:
        if claims is None:
            claims = split_claims(text)

        if not claims:
            return DetectorOutput(
                detector_name=self.name,
                overall_score=0.0,
                meta={"reason": "未检测到可验证声明"},
            )

        # 构造判定 prompt
        claim_results = []
        scores = []

        for claim in claims:
            support_count = 0
            judgments = []

            for sample_idx in range(self.num_samples):
                prompt = self._build_judge_prompt(claim, text, sample_idx)
                responses = self.llm.generate(
                    prompt, n=1, temperature=0.0
                )
                judgment = responses[0].text.strip().upper()
                is_supported = judgment.startswith("YES")
                judgments.append(is_supported)
                if is_supported:
                    support_count += 1

            support_ratio = support_count / self.num_samples
            hallucination_score = 1.0 - support_ratio

            claim_results.append(
                ClaimResult(
                    claim=claim,
                    score=hallucination_score,
                    detail=f"支持: {support_count}/{self.num_samples}",
                    evidence={
                        "support_ratio": support_ratio,
                        "judgments": judgments,
                    },
                )
            )
            scores.append(hallucination_score)

        overall = max(scores) if scores else 0.0

        return DetectorOutput(
            detector_name=self.name,
            overall_score=overall,
            claim_results=claim_results,
            meta={
                "num_samples": self.num_samples,
                "avg_score": sum(scores) / len(scores) if scores else 0,
            },
        )

    def _build_judge_prompt(
        self, claim: str, context: str, sample_idx: int
    ) -> str:
        return (
            "请判断以下声明是否被上下文所支持。\n"
            "只回答 YES 或 NO，不要解释。\n\n"
            f"声明: {claim}\n\n"
            f"上下文: {context}\n\n"
            "声明是否被上下文支持? (YES/NO):"
        )
