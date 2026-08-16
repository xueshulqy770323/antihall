# -*- coding: utf-8 -*-
"""示例 1: 基本用法 — 检测金融文本中的幻觉（v3.0 双引擎模式）。

本示例展示两种模式：
  1. 纯正则模式（免费，无需 API Key）
  2. LLM 增强模式（需 API Key，启用语义检测）

运行前请先安装依赖：
    pip install akshare           # 数据源（必需）
    pip install openai            # LLM 语义检测（可选）

运行：
    python examples/basic_usage.py
"""
import os
from antihall import HallucinationChecker
from antihall.llm.client import LLMConfig


# ── 待检测文本 ──────────────────────────────────────────────
# 包含数字幻觉 + 语义幻觉的混合示例
SAMPLE_TEXT = (
    "贵州茅台2023年营收1505.6亿元，同比增长18.0%。"
    "比亚迪2023年净利润300.4亿元，同比增长80.7%。"
    "宁德时代2023年净利润4001.2亿元，同比增长43.6%。"  # 4001.2 是编的
    "茅台营收连续三年增长。"  # 语义声明：趋势验证
)

# LLM 配置（留空则纯数字模式，填入则启用语义检测）
# 支持 OpenAI / DeepSeek / Qwen / GLM 等 OpenAI 兼容 API
LLM_API_KEY = os.environ.get("ANTIHALL_LLM_KEY", "")      # 从环境变量读取
LLM_BASE_URL = os.environ.get("ANTIHALL_LLM_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.environ.get("ANTIHALL_LLM_MODEL", "deepseek-chat")


def demo_regex_only():
    """模式一：纯正则检测（免费，无需 API Key）。"""
    print("=" * 60)
    print("模式一：纯正则检测（数字核查）")
    print("=" * 60)
    print(f"\n【待检测文本】\n{SAMPLE_TEXT}\n")

    checker = HallucinationChecker()
    result = checker.check(SAMPLE_TEXT)

    print("【检测结果摘要】")
    print(result.summary())
    print(f"风险等级: {result.risk_level}\n")

    _print_details(result)

    html_path = os.path.join(
        os.path.dirname(__file__), "..", "report_regex.html"
    )
    checker.check_and_report(SAMPLE_TEXT, html_path, "幻觉检测报告（纯正则模式）")
    print(f"\nHTML 报告已保存: {os.path.abspath(html_path)}\n")


def demo_llm_enhanced():
    """模式二：LLM 增强检测（数字 + 语义双重核查）。"""
    if not LLM_API_KEY:
        print("=" * 60)
        print("模式二：LLM 增强检测（已跳过）")
        print("=" * 60)
        print("未配置 LLM API Key。设置环境变量 ANTIHALL_LLM_KEY 即可启用：")
        print("  export ANTIHALL_LLM_KEY=sk-xxx")
        print("  export ANTIHALL_LLM_URL=https://api.deepseek.com/v1  # 可选")
        print("  export ANTIHALL_LLM_MODEL=deepseek-chat              # 可选\n")
        return

    print("=" * 60)
    print("模式二：LLM 增强检测（数字 + 语义双重核查）")
    print("=" * 60)
    print(f"\n【待检测文本】\n{SAMPLE_TEXT}\n")

    checker = HallucinationChecker(
        llm_config=LLMConfig(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            model=LLM_MODEL,
        )
    )
    result = checker.check(SAMPLE_TEXT)

    print("【检测结果摘要】")
    print(result.summary())
    print(f"风险等级: {result.risk_level}\n")

    _print_details(result)

    html_path = os.path.join(
        os.path.dirname(__file__), "..", "report_llm.html"
    )
    checker.check_and_report(SAMPLE_TEXT, html_path, "幻觉检测报告（LLM 增强模式）")
    print(f"\nHTML 报告已保存: {os.path.abspath(html_path)}\n")


def _print_details(result):
    """逐条打印检测详情。"""
    print("【逐条核查详情】")
    print("-" * 60)
    for i, report in enumerate(result.claims, 1):
        print(f"\n第 {i} 条: [{report.verdict.value}]")
        print(f"  原文: {report.claim.raw_text}")

        if report.semantic_type:
            print(f"  语义类型: {report.semantic_type.value}")

        if hasattr(report.claim, "entity") and report.claim.entity:
            print(f"  公司: {report.claim.entity}")
        if hasattr(report.claim, "metric") and report.claim.metric:
            print(f"  指标: {report.claim.metric}")
        if hasattr(report.claim, "value") and report.claim.value:
            print(f"  声称值: {report.claim.value}{report.claim.unit}")

        if report.evidence:
            print(f"  真实值: {report.evidence.actual_value}{report.evidence.unit}")
            print(f"  数据源: {report.evidence.source_name}")
            if report.evidence.url:
                print(f"  证据链接: {report.evidence.url}")

        if report.deviation is not None:
            if hasattr(report.claim, "metric") and report.claim.metric.startswith("同比"):
                print(f"  偏差: {abs(report.deviation):.1f}个百分点")
            else:
                print(f"  偏差: {abs(report.deviation):.1%}")

        if report.explanation:
            print(f"  解释: {report.explanation}")
        if report.suggestion:
            print(f"  建议: {report.suggestion}")
        print("-" * 60)


if __name__ == "__main__":
    demo_regex_only()
    demo_llm_enhanced()
