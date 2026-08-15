---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: 'd3115091-46f4-4fbf-affe-9c3049093691'
  PropagateID: 'd3115091-46f4-4fbf-affe-9c3049093691'
  ReservedCode1: '95b45da1-4a0e-434e-ad20-608217b3068d'
  ReservedCode2: '95b45da1-4a0e-434e-ad20-608217b3068d'
---

# antihall

> AI 幻觉检测工具库 — 用 AI 对抗 AI 的幻觉

`antihall` 是一个 Python 工具库，用于检测大语言模型 (LLM) 输出中的**幻觉** (hallucination)——即模型编造事实、给出错误信息、或无中生有引用不存在内容的现象。

---

## 这是什么

LLM 会"自信地胡说"。`antihall` 提供多种互补的检测策略，帮你识别 LLM 输出中哪些声明可能是幻觉。

### 三大检测器

| 检测器 | 原理 | 适用场景 |
|--------|------|---------|
| **Self-Consistency** (自洽性) | 对同一问题多次采样，交叉验证回答一致性。不一致 → 可能是幻觉 | 任何生成式回答 |
| **Confidence** (置信度) | 利用 token-level logprobs 评估模型对每个词的"自信程度" | 支持 logprobs 的 API (如 OpenAI) |
| **Fact-Check** (事实核查) | 对每条声明检索外部知识源 (Wikipedia/自定义 RAG)，用 NLI 判定是否被证据支持 | 需要外部验证的事实性陈述 |

### 论文基础

- **Self-Consistency**: SelfCheckGPT (Manakul et al., EMNLP 2023) [arxiv:2303.08896](https://arxiv.org/abs/2303.08896)
- **Confidence**: "Language Models (Mostly) Know What They Know" (Kadavath et al., 2022) [arxiv:2207.05221](https://arxiv.org/abs/2207.05221)
- **Fact-Check**: FacTool (Chern et al., 2023) [arxiv:2307.13528](https://arxiv.org/abs/2307.13528)

---

## 快速开始

### 安装

```bash
pip install antihall
```

或从源码安装:

```bash
git clone https://github.com/xueshulqy770323/antihall.git
cd antihall
pip install -e .
```

### 基础用法

```python
from antihall import HallucinationDetector

# 初始化检测器
detector = HallucinationDetector(api_key="sk-your-openai-key")

# 检测文本
text = """
巴黎是法国的首都。
2024年夏季奥运会在巴黎举办。
巴黎人口超过2000万，是世界最大城市。
"""

result = detector.check(text)

# 查看结果
print(result)
# 输出:
# ========================================
# 幻觉检测报告
# 综合评分: 45.00%
# 风险等级: medium
# 被标记声明数: 2
#
# 高风险声明:
#   1. [80.00%] 巴黎人口超过2000万，是世界最大城市
#      - fact_check: 证据不支持
#      - self_consistency: 支持: 1/5
# ...
```

### 只用事实核查 (+自定义 RAG 知识库)

```python
from antihall.detectors import FactCheckDetector
from antihall.utils.llm_client import LLMClient

def my_rag_search(query: str) -> list[str]:
    # 从你的向量数据库 / Elasticsearch 检索
    ...

llm = LLMClient(api_key="sk-xxx")
checker = FactCheckDetector(llm_client=llm, search_fn=my_rag_search)
result = checker.detect("某条需要验证的文本")
```

### 使用自定义模型 (非 OpenAI)

```python
from antihall import HallucinationDetector
from antihall.utils.llm_client import LLMClient, LLMResponse

def my_api(prompt: str, **kwargs) -> LLMResponse:
    # 调用你自己的模型 API
    ...

client = LLMClient(provider="custom", llm_fn=my_api)
detector = HallucinationDetector(llm_client=client)
```

---

## 项目结构

```
antihall/
├── antihall/
│   ├── __init__.py          # 包入口
│   ├── core.py              # HallucinationDetector 主接口
│   ├── detectors/
│   │   ├── base.py          # 检测器基类
│   │   ├── self_consistency.py   # 自洽性检测 (SelfCheckGPT)
│   │   ├── confidence.py    # logprob 置信度检测
│   │   └── fact_check.py    # 事实核查 + Wikipedia/RAG
│   ├── verifiers/
│   │   └── aggregator.py    # 多检测器结果聚合
│   └── utils/
│       ├── llm_client.py    # LLM 客户端抽象层
│       └── text.py          # 文本句切 / claim 提取
├── tests/
│   ├── test_text.py
│   └── test_aggregator.py
├── examples/
│   ├── basic_usage.py
│   ├── custom_llm.py
│   └── batch_and_rag.py
├── pyproject.toml
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 检测结果说明

`DetectionResult` 对象包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| `overall_score` | float | 综合幻觉评分 0~1，越高越可能含幻觉 |
| `risk_level` | str | 风险等级: low / medium / high |
| `flagged_claims` | list | 被标记为高风险的声明列表，含各检测器的分数和说明 |
| `detector_outputs` | list | 各检测器的详细输出 |
| `to_json()` | str | 转为 JSON 字符串 |

---

## 配置

### 检测器权重

默认权重: self_consistency 40%, fact_check 40%, confidence 20%

```python
detector = HallucinationDetector(
    api_key="sk-xxx",
    weights={"self_consistency": 0.5, "fact_check": 0.5, "confidence": 0.0},
)
```

### 只启用部分检测器

```python
detector = HallucinationDetector(
    api_key="sk-xxx",
    detectors=["fact_check", "self_consistency"],
)
```

---

## 限制与已知问题

1. **自洽性检测需要多次 API 调用**: 默认采样 5 次，成本和延迟较高。可通过 `num_samples` 参数降低。
2. **置信度检测依赖 logprobs**: 目前仅 OpenAI API 原生支持。Anthropic 等不支持返回 logprobs 的提供商无法使用此检测器。
3. **事实核查依赖外部知识源**: 对非常识性/时效性问题，Wikipedia 可能无法覆盖，建议接入自定义 RAG。
4. **幻觉检测本身不完美**: 本工具可显著降低幻觉风险，但不能 100% 消除。请结合人工审核使用。
5. **中文/多语言支持**: 文本拆分已支持中英文，但 NLI 判定 prompt 的效果取决于所用 LLM 的语言能力。

---

## 贡献

欢迎提交 Issue 和 PR。

```bash
# 开发环境
git clone https://github.com/xueshulqy770323/antihall.git
cd antihall
pip install -e ".[dev]"

# 运行测试
pytest tests/
```

## License

MIT

> AI生成