# -*- coding: utf-8 -*-
"""
事实核查检测器 (Fact-Check Detector)

核心思路:
  1. 从文本中提取可验证的事实声明 (claim)
  2. 对每个 claim，调用外部知识源 (搜索引擎/Wikipedia API) 检索相关证据
  3. 用 LLM 判断 claim 是否被证据支持
  4. 不被证据支持的 claim → 可能是幻觉

外部知识源:
  - Wikipedia API (默认，免费，无需 key)
  - 自定义检索函数 (可接入 RAG 知识库)

参考: "FacTool: Factuality Detection in Generative AI" (Chern et al., 2023)
https://arxiv.org/abs/2307.13528
"""

from typing import List, Optional, Callable
import json
import urllib.request
import urllib.parse

from .base import BaseDetector, DetectorOutput, ClaimResult
from ..utils.llm_client import LLMClient
from ..utils.text import split_claims


class FactCheckDetector(BaseDetector):
    """
    事实核查检测器

    Parameters
    ----------
    llm_client : LLMClient
        LLM 客户端 (用于 claim 提取和 NLI 判定)
    search_fn : callable, optional
        自定义搜索函数: (query: str) -> List[str]
        如不提供，默认使用 Wikipedia API
    max_evidence_per_claim : int
        每个 claim 检索的最大证据条数 (默认 3)
    language : str
        搜索语言: "en" 或 "zh" (默认 "en")
    """

    name = "fact_check"

    def __init__(
        self,
        llm_client: LLMClient,
        search_fn: Optional[Callable[[str], List[str]]] = None,
        max_evidence_per_claim: int = 3,
        language: str = "en",
    ):
        self.llm = llm_client
        self._search_fn = search_fn or self._wikipedia_search
        self.max_evidence = max_evidence_per_claim
        self.language = language

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

        claim_results = []
        scores = []

        for claim in claims:
            # 1. 搜索证据
            query = self._extract_search_query(claim)
            evidences = self._search_fn(query)

            if not evidences:
                claim_results.append(
                    ClaimResult(
                        claim=claim,
                        score=0.5,  # 无法找到证据，给中等风险分
                        detail="未找到相关证据，无法验证",
                        evidence={"found_evidence": False},
                    )
                )
                scores.append(0.5)
                continue

            # 2. 用 LLM 判断 claim 是否被证据支持 (NLI 判定)
            prompt = self._build_nli_prompt(claim, evidences)
            responses = self.llm.generate(prompt, n=1, temperature=0.0)
            judgment = responses[0].text.strip()

            is_supported = judgment.upper().startswith("YES")
            score = 0.0 if is_supported else 0.8

            claim_results.append(
                ClaimResult(
                    claim=claim,
                    score=score,
                    detail="被证据支持" if is_supported else "证据不支持",
                    evidence={
                        "search_query": query,
                        "evidence_snippets": evidences[: self.max_evidence],
                        "judgment": judgment,
                    },
                )
            )
            scores.append(score)

        overall = max(scores) if scores else 0.0

        return DetectorOutput(
            detector_name=self.name,
            overall_score=overall,
            claim_results=claim_results,
            meta={
                "num_claims": len(claims),
                "num_verified": sum(
                    1 for r in claim_results if r.score == 0.0
                ),
                "num_unverified": sum(
                    1 for r in claim_results if r.score > 0
                ),
            },
        )

    def _wikipedia_search(self, query: str) -> List[str]:
        """使用 Wikipedia API 搜索""" 
        lang = self.language
        search_url = f"https://{lang}.wikipedia.org/w/api.php"

        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": str(self.max_evidence),
        }

        url = f"{search_url}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "antihall/0.1 (research tool)"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = []
            for item in data.get("query", {}).get("search", []):
                snippet = item.get("snippet", "")
                # 去掉 HTML 标签
                import re
                snippet = re.sub(r"<[^>]+>", "", snippet)
                results.append(snippet)

            return results
        except Exception as e:
            return []

    def _extract_search_query(self, claim: str) -> str:
        """
        从 claim 中提取搜索关键词

        简化方案: 直接用 claim 前半段作为查询。
        未来可用 LLM 做更好的关键词提取。
        """
        # 取 claim 的前100字符作为搜索 query
        return claim[:100]

    def _build_nli_prompt(
        self, claim: str, evidences: List[str]
    ) -> str:
        evidence_text = "\n".join(
            f"[{i+1}] {e}" for i, e in enumerate(evidences)
        )
        return (
            "请根据以下证据判断声明是否被支持。\n"
            "只回答 YES (支持) 或 NO (不支持或矛盾)，不要解释。\n\n"
            f"声明: {claim}\n\n"
            f"证据:\n{evidence_text}\n\n"
            "声明是否被以上证据支持? (YES/NO):"
        )
