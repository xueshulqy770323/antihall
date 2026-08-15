# -*- coding: utf-8 -*-
"""
LLM 客户端抽象层

统一封装不同 LLM 提供商的调用接口，让上层检测器无需关心具体 API 差异。
当前支持:
  - OpenAI (gpt-4o, gpt-4o-mini, gpt-3.5-turbo 等)
  - Anthropic (claude-3.5-sonnet, claude-3-haiku 等)  [可选]
  - 自定义回调函数

如果你使用的模型提供商不在此列，可以传入一个 callable 作为 llm_fn。
"""

import os
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """LLM 调用的统一返回结构"""
    text: str
    logprobs: Optional[List[Dict[str, Any]]] = None
    raw: Optional[Any] = None


class LLMClient:
    """
    LLM 客户端封装

    Parameters
    ----------
    api_key : str
        API 密钥 (OpenAI 或 Anthropic)
    provider : str
        提供商: "openai" / "anthropic" / "custom"
    model : str
        模型名称，如 "gpt-4o-mini"
    llm_fn : callable, optional
        自定义调用函数，签名: (prompt: str, **kwargs) -> LLMResponse
        provider="custom" 时必须提供
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        llm_fn: Optional[Callable] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        base_url: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base_url = base_url
        self._llm_fn = llm_fn

        if provider == "custom":
            if llm_fn is None:
                raise ValueError("provider='custom' 时必须提供 llm_fn 参数")
            return

        # 解析 API key
        if api_key is None:
            if provider == "openai":
                api_key = os.environ.get("OPENAI_API_KEY")
            elif provider == "anthropic":
                api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key is None:
            raise ValueError(
                f"未找到 API key。请传入 api_key 参数，或设置环境变量 "
                f"{'OPENAI_API_KEY' if provider == 'openai' else 'ANTHROPIC_API_KEY'}"
            )
        self.api_key = api_key

    def generate(
        self,
        prompt: str,
        n: int = 1,
        return_logprobs: bool = False,
        temperature: Optional[float] = None,
    ) -> List[LLMResponse]:
        """
        生成回复

        Parameters
        ----------
        prompt : str
            输入提示词
        n : int
            生成几条回复 (用于自洽性检测时需要 n>1)
        return_logprobs : bool
            是否返回 token 级别的 logprobs
        temperature : float, optional
            覆盖默认温度

        Returns
        -------
        List[LLMResponse]
        """
        if self.provider == "custom":
            responses = []
            for _ in range(n):
                resp = self._llm_fn(
                    prompt,
                    return_logprobs=return_logprobs,
                    temperature=temperature or self.temperature,
                )
                if isinstance(resp, LLMResponse):
                    responses.append(resp)
                elif isinstance(resp, str):
                    responses.append(LLMResponse(text=resp))
                else:
                    raise TypeError("自定义 llm_fn 必须返回 str 或 LLMResponse")
            return responses

        if self.provider == "openai":
            return self._generate_openai(
                prompt, n, return_logprobs, temperature
            )

        if self.provider == "anthropic":
            return self._generate_anthropic(
                prompt, n, return_logprobs, temperature
            )

        raise ValueError(f"不支持的 provider: {self.provider}")

    def _generate_openai(
        self, prompt, n, return_logprobs, temperature
    ) -> List[LLMResponse]:
        """调用 OpenAI API"""
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "n": n,
            "temperature": temperature or self.temperature,
            "max_tokens": self.max_tokens,
        }
        if return_logprobs:
            kwargs["logprobs"] = True
            kwargs["top_logprobs"] = 5

        completion = client.chat.completions.create(**kwargs)

        results = []
        for choice in completion.choices:
            text = choice.message.content or ""
            logprobs_data = None
            if return_logprobs:
                lp = choice.logprobs
                if lp:
                    logprobs_data = [
                        {
                            "token": item.token,
                            "logprob": item.logprob,
                            "text": item.token,
                        }
                        for item in lp.content or []
                    ]
            results.append(
                LLMResponse(text=text, logprobs=logprobs_data, raw=choice)
            )
        return results

    def _generate_anthropic(
        self, prompt, n, return_logprobs, temperature
    ) -> List[LLMResponse]:
        """
        调用 Anthropic API

        注意: Anthropic 不支持 n>1 的一次性多采样，需要循环调用。
        且不直接返回 token logprobs，return_logprobs 参数在此提供商下
        会被忽略 (返回 None)。
        """
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "使用 Anthropic 需要安装: pip install anthropic"
            )

        client = anthropic.Anthropic(api_key=self.api_key)

        results = []
        for _ in range(n):
            message = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=temperature or self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text if message.content else ""
            results.append(LLMResponse(text=text, logprobs=None, raw=message))
        return results
