"""antihall — 中文金融报告幻觉检测工具包。

检测 LLM 生成的中文金融文本中的数字幻觉，
通过对接真实财报数据（AKShare）进行验证，
输出可解释的检测结果（哪句有问题、为什么、怎么改）。
"""

from antihall.core import HallucinationChecker, CheckResult, ClaimReport

__version__ = "2.0.0"
__all__ = ["HallucinationChecker", "CheckResult", "ClaimReport"]
