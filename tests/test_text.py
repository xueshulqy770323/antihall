# -*- coding: utf-8 -*-
"""Tests for text utility functions"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from antihall.utils.text import (
    split_sentences,
    split_claims,
    extract_numbers,
    normalize_text,
)


def test_split_sentences_chinese():
    text = "巴黎是法国的首都。面积约为105平方公里。它是欧洲最大的城市之一！"
    sentences = split_sentences(text)
    assert len(sentences) == 3
    assert "巴黎是法国的首都" in sentences[0]


def test_split_sentences_english():
    text = "Paris is the capital of France. It has an area of 105 sq km."
    sentences = split_sentences(text)
    assert len(sentences) == 2


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_split_claims_min_length():
    text = "OK。这是一个足够长的声明。短。"
    claims = split_claims(text, min_length=10)
    assert len(claims) == 1


def test_extract_numbers():
    text = "2024年有365天，温度36.5度"
    numbers = extract_numbers(text)
    assert "2024" in numbers
    assert "365" in numbers
    assert "36.5" in numbers


def test_normalize_text():
    text = "  多个   空格\n\n和换行  "
    assert normalize_text(text) == "多个 空格 和换行"


if __name__ == "__main__":
    test_split_sentences_chinese()
    test_split_sentences_english()
    test_split_sentences_empty()
    test_split_claims_min_length()
    test_extract_numbers()
    test_normalize_text()
    print("All text utility tests passed!")
