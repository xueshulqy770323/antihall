# -*- coding: utf-8 -*-
"""
批量检测示例 + RAG 知识库接入示例
"""

from antihall import HallucinationDetector
from antihall.detectors import FactCheckDetector


# === 批量检测 ===
detector = HallucinationDetector(api_key="sk-your-api-key")

texts = [
    "北京是中国的首都。",
    "珠穆朗玛峰高度为8848.86米。",
    "太阳系有12颗行星。",  # 错误，应为8颗
    "中国长城总长度超过21000公里。",
]

results = detector.check_batch(texts)
for i, (text, result) in enumerate(zip(texts, results), 1):
    print(f"\n[{i}] {text}")
    print(f"    幻觉评分: {result.overall_score:.2%} | 风险: {result.risk_level}")


# === 接入自定义 RAG 知识库 ===
print("\n" + "=" * 60)
print("接入自定义 RAG 知识库示例")
print("=" * 60)


def my_rag_search(query: str) -> list[str]:
    """
    自定义搜索函数: 从你的 RAG 知识库中检索

    这里只是示例。实际使用时替换为你的检索逻辑，比如:
    - 从向量数据库 (ChromaDB, FAISS, Pinecone) 检索
    - 从 Elasticsearch 搜索
    - 调用你自己的搜索 API
    """
    # 模拟检索结果
    knowledge_base = {
        "北京": ["北京是中华人民共和国的首都，位于华北平原。"],
        "珠峰": ["珠穆朗玛峰海拔8848.86米，是世界最高峰。"],
    }

    for key, docs in knowledge_base.items():
        if key in query:
            return docs
    return []


# 仅使用事实核查检测器，接入自定义 RAG
from antihall.utils.llm_client import LLMClient

llm = LLMClient(api_key="sk-your-api-key")
fact_checker = FactCheckDetector(
    llm_client=llm,
    search_fn=my_rag_search,
)

result = fact_checker.detect("北京是中国最大的城市，人口超过5000万。")
print(f"整体幻觉评分: {result.overall_score:.2%}")
for cr in result.claim_results:
    print(f"  [{cr.score:.2%}] {cr.claim}")
    print(f"       {cr.detail}")
