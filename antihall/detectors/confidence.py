# -*- coding: utf-8 -*-
"""
置信度检测器 (Confidence Detector)

核心思路:
  利用 LLM 返回的 token-level logprobs 评估模型对每个 token 的置信度。
  如果某些关键 token 的 logprob 很低 (概率很低)，说明模型"心虚"，
  这些位置可能对应幻觉内容。

适用条件:
  - 需要使用支持返回 logprobs 的 API (如 OpenAI)
  - 文本需要是由同一个 LLM 生成的 (而非用户手写的)

参考: "Language Models (Mostly) Know What They Know" (Kadavath et al., 2022)
https://arxiv.org/abs/2207.05221
"""

from typing import List, Optional
import math

from .base import BaseDetector, DetectorOutput, ClaimResult
from ..utils.llm_client import LLMClient
from ..utils.text import split_claims


class ConfidenceDetector(BaseDetector):
    """
    基于 token logprob 的置信度检测器

    Parameters
    ----------
    llm_client : LLMClient
        LLM 客户端 (必须支持 logprobs)
    low_confidence_threshold : float
        低置信度阈值 (概率)。token 概率低于此值视为"不确定" (默认 0.3)
    """

    name = "confidence"

    def __init__(
        self,
        llm_client: LLMClient,
        low_confidence_threshold: float = 0.3,
    ):
        self.llm = llm_client
        self.threshold = low_confidence_threshold

    def detect(
        self, text: str, claims: List[str] = None
    ) -> DetectorOutput:
        if claims is None:
            claims = split_claims(text)

        # 重新请求 LLM 生成同一段文本，获取 logprobs
        # 用 text 本身作为 prompt 的回复部分，获取每个 token 的概率
        prompt = f"请复述以下内容:\n{text}"

        responses = self.llm.generate(
            prompt,
            n=1,
            return_logprobs=True,
            temperature=0.0,
        )

        response = responses[0]
        logprobs = response.logprobs

        if logprobs is None:
            return DetectorOutput(
                detector_name=self.name,
                overall_score=0.0,
                meta={
                    "reason": "LLM 未返回 logprobs，无法进行置信度分析。"
                    "请确保使用支持 logprobs 的 API (如 OpenAI)。"
                },
                claim_results=[
                    ClaimResult(
                        claim=c,
                        score=0.0,
                        detail="无法获取 logprobs",
                    )
                    for c in claims
                ],
            )

        # 计算每个 token 的概率
        token_probs = []
        for item in logprobs:
            logprob = item.get("logprob", 0)
            prob = math.exp(logprob)
            token_probs.append(prob)

        # 整体置信度
        avg_prob = sum(token_probs) / len(token_probs) if token_probs else 1.0
        low_conf_ratio = (
            sum(1 for p in token_probs if p < self.threshold)
            / len(token_probs)
            if token_probs
            else 0
        )

        # 整体幻觉分数: 低置信 token 比例越高，幻觉风险越大
        overall_score = min(low_conf_ratio * 2.0, 1.0)

        # 为每个 claim 分配分数 (简化方案: 统一使用整体分数)
        claim_results = [
            ClaimResult(
                claim=c,
                score=overall_score,
                detail=f"平均token概率: {avg_prob:.4f}, 低置信比例: {low_conf_ratio:.2%}",
                evidence={
                    "avg_prob": avg_prob,
                    "low_confidence_ratio": low_conf_ratio,
                },
            )
            for c in claims
        ]

        return DetectorOutput(
            detector_name=self.name,
            overall_score=overall_score,
            claim_results=claim_results,
            meta={
                "avg_token_prob": avg_prob,
                "low_confidence_token_ratio": low_conf_ratio,
                "total_tokens": len(token_probs),
            },
        )
