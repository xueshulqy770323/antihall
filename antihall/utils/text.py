# -*- coding: utf-8 -*-
"""文本处理工具"""

import re
from typing import List

# 中文标点直接断句；英文句号需后跟空格或换行（避免切断小数如 3.14）
_SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？!?；;\n]+|(?<=\.)\s+")


def split_sentences(text: str) -> List[str]:
    """
    将文本拆分为句子列表

    支持中文和英文标点。空句子会被过滤。

    Parameters
    ----------
    text : str
        输入文本

    Returns
    -------
    List[str]
        句子列表
    """
    if not text or not text.strip():
        return []
    parts = _SENTENCE_SPLIT_PATTERN.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def split_claims(text: str, min_length: int = 10) -> List[str]:
    """
    将文本拆分为可验证的事实声明 (claim) 列表

    每个 claim 是一个可以单独验证的断言。
    目前采用简单的按句拆分策略; 后续可接入更复杂的 claim extraction。

    Parameters
    ----------
    text : str
        输入文本
    min_length : int
        声明的最小长度 (字符)，过短的碎片会被过滤

    Returns
    -------
    List[str]
    """
    sentences = split_sentences(text)
    return [s for s in sentences if len(s) >= min_length]


def extract_numbers(text: str) -> List[str]:
    """
    从文本中提取数字 (用于数值核查)

    Returns
    -------
    List[str]
        文本中出现的数字字符串列表
    """
    return re.findall(r"\d+\.?\d*", text)


def normalize_text(text: str) -> str:
    """
    文本归一化: 去除多余空白、统一标点

    Parameters
    ----------
    text : str

    Returns
    -------
    str
    """
    text = re.sub(r"\s+", " ", text.strip())
    return text
