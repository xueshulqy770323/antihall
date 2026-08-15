"""示例 2: 批量检测多段文本 + 生成综合 HTML 报告。

运行：
    python examples/batch_check.py
"""
import os

from antihall import HallucinationChecker


def main():
    # 多段待检测文本（模拟 LLM 生成的研报摘要）
    texts = [
        "贵州茅台2023年营收1505.6亿元。",
        "比亚迪2023年净利润300.4亿元，同比增长80.7%。",
        "宁德时代2023年营收4009.2亿元。",       # 真实值约 4009亿
        "中国平安2023年净利润856.6亿元。",       # 编造的数字
        "招商银行2023年营收3391.2亿元。",         # 编造的数字
    ]

    checker = HallucinationChecker()

    all_results = []
    for i, text in enumerate(texts, 1):
        print(f"[{i}/{len(texts)}] 检测中...")
        result = checker.check(text)
        all_results.append(result)
        print(f"  {result.summary()}")

    # 汇总统计
    total_claims = sum(r.total_claims for r in all_results)
    total_halluc = sum(r.hallucinated_count for r in all_results)
    total_correct = sum(r.correct_count for r in all_results)
    total_unverifiable = sum(r.unverifiable_count for r in all_results)
    verified = total_correct + total_halluc
    rate = total_halluc / verified if verified else 0

    print("\n" + "=" * 60)
    print("批量检测汇总")
    print("=" * 60)
    print(f"总计检测 {len(texts)} 段文本，{total_claims} 条声明")
    print(f"  幻觉: {total_halluc}")
    print(f"  正确: {total_correct}")
    print(f"  无法验证: {total_unverifiable}")
    print(f"  幻觉率: {rate:.1%}")

    # 将第一段文本作为示例生成 HTML 报告
    if all_results:
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "batch_report.html"
        )
        checker.check_and_report(
            "\n".join(texts), report_path, "批量金融幻觉检测报告"
        )
        print(f"\nHTML 报告已保存: {os.path.abspath(report_path)}")


if __name__ == "__main__":
    main()
