# -*- coding: utf-8 -*-
"""
antihall 基础用法示例

运行前请安装: pip install openai
并设置环境变量: OPENAI_API_KEY=sk-xxx
"""

from antihall import HallucinationDetector

# 初始化检测器
detector = HallucinationDetector(
    api_key="sk-your-api-key",  # 或设置环境变量 OPENAI_API_KEY
    provider="openai",
    model="gpt-4o-mini",
)

# 测试文本
text = """
巴黎是法国的首都，位于法国北部塞纳河畔。
巴黎面积约为105平方公里，是欧洲最大的城市之一。
2024年夏季奥运会在巴黎举办。
巴黎的人口超过2000万，是世界上人口最多的城市。
"""

# 执行检测
result = detector.check(text)

# 查看结果
print(result)
print("\n--- JSON 格式 ---")
print(result.to_json())

# 也可以只启用部分检测器
detector_fc_only = HallucinationDetector(
    api_key="sk-your-api-key",
    detectors=["fact_check"],
)
