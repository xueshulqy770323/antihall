# -*- coding: utf-8 -*-
"""
自定义 LLM 客户端示例

如果你使用的模型不是 OpenAI/Anthropic（如国内大模型 API），
可以通过 provider="custom" 传入自定义调用函数。
"""

from antihall import HallucinationDetector
from antihall.utils.llm_client import LLMClient, LLMResponse


def my_custom_llm(prompt: str, **kwargs) -> LLMResponse:
    """
    自定义 LLM 调用函数

    这里用简单的 echo 做演示，实际使用时替换为你的 API 调用。
    """
    # 示例: 调用你自己的模型 API
    # response = requests.post("https://your-api.com/v1/chat", json={"prompt": prompt})
    # return LLMResponse(text=response.json()["text"])

    # 演示用: 简单返回
    return LLMResponse(text="YES")


# 创建自定义客户端
custom_client = LLMClient(
    provider="custom",
    llm_fn=my_custom_llm,
    model="my-model",
)

# 用自定义客户端创建检测器
detector = HallucinationDetector(llm_client=custom_client)

# 执行检测
result = detector.check("地球是太阳系中第三颗行星。")
print(result)
