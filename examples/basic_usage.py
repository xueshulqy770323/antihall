"""示例 1: 基本用法 — 检测一段金融文本中的幻觉。

运行前请先安装依赖：
    pip install akshare

运行：
    python examples/basic_usage.py
"""
from antihall import HallucinationChecker


def main():
    # 一段 LLM 生成的金融分析文本（其中有些数字是编造的）
    text = (
        "贵州茅台2023年营收1505.6亿元，同比增长18.0%。"
        "比亚迪2023年净利润300.4亿元，同比增长80.7%。"
        "宁德时代2023年净利润4001.2亿元，同比增长43.6%。"  # 4001.2 是编的
    )

    print("=" * 60)
    print("金融报告幻觉检测")
    print("=" * 60)
    print(f"\n【待检测文本】\n{text}\n")

    # 检测
    checker = HallucinationChecker()
    result = checker.check(text)

    # 打印摘要
    print("【检测结果摘要】")
    print(result.summary())
    print(f"风险等级: {result.risk_level}\n")

    # 逐条详情
    print("【逐条核查详情】")
    print("-" * 60)
    for i, report in enumerate(result.claims, 1):
        print(f"\n第 {i} 条: [{report.verdict.value}]")
        print(f"  原文: {report.claim.raw_text}")
        print(f"  公司: {report.claim.entity}")
        print(f"  指标: {report.claim.metric}")
        print(f"  声称值: {report.claim.value}{report.claim.unit}")

        if report.evidence:
            print(f"  真实值: {report.evidence.actual_value}{report.evidence.unit}")
            print(f"  数据源: {report.evidence.source_name}")
            print(f"  证据链接: {report.evidence.url}")

        if report.deviation is not None:
            if report.claim.metric.startswith("同比"):
                print(f"  偏差: {abs(report.deviation):.1f}个百分点")
            else:
                print(f"  偏差: {abs(report.deviation):.1%}")

        if report.explanation:
            print(f"  解释: {report.explanation}")
        if report.suggestion:
            print(f"  建议: {report.suggestion}")
        print("-" * 60)

    # 生成 HTML 报告
    import os
    report_path = os.path.join(
        os.path.dirname(__file__), "..", "hallucination_report.html"
    )
    checker.check_and_report(text, report_path, "金融报告幻觉检测 — 示例")
    print(f"\nHTML 报告已保存: {os.path.abspath(report_path)}")


if __name__ == "__main__":
    main()
