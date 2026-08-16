---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '14734fbe-2c92-4306-8aa2-9febcb1a7634'
  PropagateID: '14734fbe-2c92-4306-8aa2-9febcb1a7634'
  ReservedCode1: '4143dafd-76f9-4fc7-9894-2959ede7afc8'
  ReservedCode2: '4143dafd-76f9-4fc7-9894-2959ede7afc8'
---

# antihall

**中文金融报告幻觉检测工具包** — 双引擎（正则 + LLM）提取金融声明，数字 + 语义双重核查，对接 A 股真实财报数据验证，输出可解释的检测结果。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version 3.0.0](https://img.shields.io/badge/version-3.0.0-green.svg)](https://github.com/xueshulqy770323/antihall)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 为什么需要 antihall？

大语言模型（LLM）在生成金融分析、投研报告时，经常编造内容——不只是数字错误，还会捏造因果逻辑、颠倒趋势、张冠李戴。这在金融场景下是致命的：一个错误的因果推论可能比数字错误更有欺骗性。

现有幻觉检测工具（SelfCheckGPT、FacTool 等）几乎全部面向英文、通用场景。**中文金融领域没有可用的开源幻觉检测工具。**

antihall v3.0 填补这个空白：

| 特性 | antihall v3 | 通用幻觉检测工具 |
|------|-------------|-----------------|
| 中文支持 | 原生中文 | 需要翻译/适配 |
| 数据源 | A 股真实财报（AKShare） | Wikipedia/英文知识库 |
| 数字检测 | 精确数字核查 + 容差判定 | 语义自洽性（模糊） |
| 语义检测 | 趋势颠倒/时间错位/指标混淆/因果编造 | 不支持 |
| 提取引擎 | 正则 + LLM 双引擎 | 单一方法 |
| 输出 | 哪句错、为什么、怎么改、证据链接 | 一个幻觉概率分数 |
| 适用场景 | 金融报告/投研分析 | 通用文本 |

---

## v3.0 新增：语义幻觉检测

v2.0 只能检测"数字对不对"。v3.0 新增四类语义幻觉检测，能抓住"数字对了但意思错了"的问题：

| 语义幻觉类型 | 示例 | 检测方法 |
|-------------|------|---------|
| **趋势颠倒** | "营收连续三年增长"（实际在下降） | 拉取多年数据，验证趋势方向 |
| **时间错位** | "2023年营收1500亿"（1500亿其实是2022年的） | 比对相邻年份，定位数字实际归属 |
| **指标混淆** | "净利润1500亿"（1500亿其实是营收） | 交叉验证其他指标，看数字匹配哪个 |
| **因果编造** | "因原材料降价，毛利率提升"（原材料其实在涨价） | 验证效果是否发生 + LLM 判断因果合理性 |

---

## 核心功能

1. **双引擎声明提取**：
   - 正则引擎（免费，无需 API Key）：提取"公司+指标+数值+年份"结构化声明
   - LLM 引擎（可选，需 API Key）：理解复杂句式、中文数字、长距离依赖，额外提取语义声明
2. **真实数据核查**：通过 AKShare 对接 A 股公开财报，获取真实数值进行比对
3. **数字幻觉检测**：单位换算 → 偏差计算 → 容差判定（营收/净利润 2%，比率 1 个百分点，增长率 5 个百分点）
4. **语义幻觉检测**：四类语义异常自动识别（趋势/时间/指标/因果）
5. **可解释判定**：不只给出"幻觉/正确"标签，还告诉你——
   - 哪句话有问题
   - 真实数据是多少
   - 偏差多大
   - 证据链接（可点击验证）
   - 修改建议（直接给出正确文本）
6. **HTML 可视化报告**：生成带高亮标注的检测报告，问题句子红色标记，语义问题附带类型标签

---

## 安装

```bash
git clone https://github.com/xueshulqy770323/antihall.git
cd antihall
pip install -e .

# 数据源依赖（必需）
pip install akshare

# LLM 语义检测依赖（可选）
pip install openai
```

---

## 快速开始

### 模式一：纯正则检测（免费，无需 API Key）

```python
from antihall import HallucinationChecker

checker = HallucinationChecker()
result = checker.check("贵州茅台2023年营收1505.6亿元，净利润862.3亿元。")
print(result.summary())
```

输出：
```
共检测 2 条声明，其中 0 条幻觉、2 条正确、0 条无法验证。幻觉率 0%，风险等级：无风险。
```

### 模式二：LLM 增强检测（完整功能，需 API Key）

```python
from antihall import HallucinationChecker
from antihall.llm.client import LLMConfig

checker = HallucinationChecker(
    llm_config=LLMConfig(
        api_key="sk-xxx",
        base_url="https://api.deepseek.com/v1",  # 支持 OpenAI 兼容 API
        model="deepseek-chat",
    )
)

text = (
    "贵州茅台2023年营收1505.6亿元。"
    "因原材料降价，毛利率大幅提升。"   # 语义声明：因果编造？
    "茅台营收连续三年增长。"          # 语义声明：趋势颠倒？
)

result = checker.check(text)
print(result.summary())

# 查看语义检测结果
for report in result.claims:
    if report.semantic_type:
        print(f"[语义] {report.semantic_type.value}: {report.verdict.value}")
        print(f"  {report.explanation}")
```

### 检测 + 生成 HTML 报告

```python
from antihall import HallucinationChecker

text = (
    "贵州茅台2023年营收1505.6亿元。"
    "宁德时代2023年净利润4001.2亿元，同比增长43.6%。"  # 4001.2 是编造的
)

checker = HallucinationChecker()
checker.check_and_report(text, "report.html", "我的检测报告")
```

打开 `report.html` 即可看到带高亮标注的可视化报告。

### 逐条查看详情

```python
for i, report in enumerate(result.claims, 1):
    print(f"第 {i} 条: [{report.verdict.value}]")
    print(f"  原文: {report.claim.raw_text}")

    if report.semantic_type:
        print(f"  语义类型: {report.semantic_type.value}")

    if hasattr(report.claim, 'value') and report.claim.value:
        print(f"  声称值: {report.claim.value}{report.claim.unit}")

    if report.evidence:
        print(f"  真实值: {report.evidence.actual_value}{report.evidence.unit}")
        print(f"  证据: {report.evidence.url}")

    if report.explanation:
        print(f"  解释: {report.explanation}")
    if report.suggestion:
        print(f"  建议: {report.suggestion}")
```

---

## 检测原理

### v3.0 统一流水线

```
输入文本
  │
  ▼
┌─────────────────────────────────────────────┐
│  Stage 1: 声明提取（双引擎并行）                 │
│  ┌─────────────┐    ┌──────────────────┐    │
│  │  正则引擎     │    │  LLM 引擎（可选）  │    │
│  │  数字声明     │    │  数字声明 + 语义声明 │    │
│  └──────┬──────┘    └────────┬─────────┘    │
│         └────────合并 + 去重──┘              │
└─────────┬───────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│  Stage 2: 数据获取                             │
│  AKShare → A 股财报（真实数值 + 多年趋势数据）    │
└─────────┬───────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│  Stage 3: 双重验证                             │
│  ┌──────────────┐  ┌────────────────────┐  │
│  │ NumericVerifier│  │ SemanticVerifier   │  │
│  │ 数字核查       │  │ 趋势/时间/指标/因果 │  │
│  └──────┬───────┘  └────────┬───────────┘  │
│         └─────────合并──────┘              │
└─────────┬───────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│  Stage 4: 解释生成                             │
│  解释 + 修改建议 + 证据链接                      │
│  → CheckResult + HTML 报告                    │
└─────────────────────────────────────────────┘
```

### 容差设定

不同指标允许的偏差范围不同：

| 指标类型 | 容差 | 原因 |
|---------|------|------|
| 营收/净利润 | 2% | 四舍五入和小数位差异 |
| 毛利率/净利率 | 1个百分点 | 比率类指标 |
| 同比增长率 | 5个百分点 | 计算基数可能不同 |

### LLM 兼容性

LLM 引擎兼容任何 OpenAI Chat Completions API 格式的服务：

| 服务 | base_url | 默认模型 |
|------|----------|---------|
| OpenAI | https://api.openai.com/v1 | gpt-4o-mini |
| DeepSeek | https://api.deepseek.com/v1 | deepseek-chat |
| 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-plus |
| 智谱 GLM | https://open.bigmodel.cn/api/paas/v4 | glm-4-flash |
| Moonshot | https://api.moonshot.cn/v1 | moonshot-v1-8k |
| 本地部署 | http://localhost:8000/v1 (vLLM/Ollama) | 自定义 |

> 未安装 `openai` 包时，自动回退到 `urllib` 原生 HTTP 请求，不影响使用。

---

## 支持的指标

| 指标 | 关键词 | 示例 |
|------|--------|------|
| 营收 | 营业收入、营收、总收入 | "贵州茅台2023年营收1505.6亿元" |
| 净利润 | 净利润、归母净利润 | "比亚迪2023年净利润300.4亿元" |
| 毛利率 | 毛利率 | "恒瑞医药2023年毛利率85%" |
| 增长率 | 同比增长、增速、增幅 | "宁德时代净利润同比增长43.6%" |
| 净利率 | 净利率 | "招商银行净利率39.5%" |
| 资产负债率 | 资产负债率 | "万科资产负债率76.5%" |
| ROE | ROE | "贵州茅台ROE 34.2%" |

### 内置公司名识别（部分）

贵州茅台、比亚迪、宁德时代、中国平安、招商银行、五粮液、隆基绿能、美的集团、格力电器、海尔智家、中国石油、中国石化、工商银行、农业银行、建设银行、中国银行、京东方、万科、恒瑞医药、药明康德、海康威视、中芯国际、长江电力、中国中免、三一重工、福耀玻璃...

不在列表中的公司会通过 AKShare 模糊搜索自动匹配。

---

## 项目结构

```
antihall/
├── antihall/
│   ├── __init__.py              # 包入口（v3.0 导出所有新类）
│   ├── core.py                  # 主接口 HallucinationChecker
│   ├── models.py                # 核心数据结构（FinancialClaim + SemanticClaim）
│   ├── pipeline.py              # v3 新增：DetectionPipeline 流水线编排
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py            # v3 新增：LLMClient（兼容 OpenAI API）
│   ├── extractor/
│   │   ├── __init__.py
│   │   ├── claim_extractor.py   # 正则引擎提取数字声明
│   │   └── llm_extractor.py     # v3 新增：LLM 语义声明提取
│   ├── datasource/
│   │   ├── __init__.py
│   │   └── akshare_source.py    # AKShare A 股财报数据源
│   ├── verifier/
│   │   ├── __init__.py
│   │   ├── numeric_verifier.py  # 数字核查引擎
│   │   └── semantic_verifier.py # v3 新增：语义验证器（4类幻觉）
│   ├── explainer/
│   │   ├── __init__.py
│   │   └── explainer.py         # 解释器（数字+语义）
│   └── report/
│       ├── __init__.py
│       └── html_report.py       # HTML 可视化报告（含语义卡片）
├── tests/
│   ├── test_extractor.py        # 正则提取器测试
│   ├── test_verifier.py         # 数字核查引擎测试
│   ├── test_explainer.py        # 解释器测试
│   ├── test_html_report.py      # HTML 报告测试
│   ├── test_llm_extractor.py    # v3 新增：LLM 提取器测试
│   └── test_semantic_verifier.py# v3 新增：语义验证器测试
├── examples/
│   ├── basic_usage.py           # 基本用法（纯正则模式）
│   └── batch_check.py           # 批量检测
├── pyproject.toml
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 运行测试

```bash
python tests/test_extractor.py
python tests/test_verifier.py
python tests/test_explainer.py
python tests/test_html_report.py
python tests/test_llm_extractor.py
python tests/test_semantic_verifier.py
```

或用 pytest：

```bash
pip install pytest
pytest tests/ -v
```

---

## 部署注意事项

1. **AKShare 依赖**：数据源依赖 [AKShare](https://github.com/akfamily/akshare)，首次使用需安装
2. **网络要求**：AKShare 通过 HTTP 请求获取数据，需能访问 A 股数据接口
3. **公司名识别**：内置 30+ 常见公司，其余靠 AKShare 模糊搜索（依赖网络）
4. **数据时效性**：财报数据取决于 AKShare 数据更新，通常 T+1 可获取最新季报
5. **LLM 可选**：不配置 `llm_config` 时自动降级为纯正则模式，功能完整但无语义检测
6. **LLM 降级**：`openai` 包未安装时自动回退到 `urllib` HTTP 请求

---

## 路线图

- [x] 正则引擎提取金融声明
- [x] AKShare 对接 A 股财报
- [x] 数字核查 + 容差判定
- [x] 可解释输出（解释+建议+证据链接）
- [x] HTML 可视化报告
- [x] LLM 辅助声明提取（v3.0）
- [x] 语义幻觉检测：趋势颠倒（v3.0）
- [x] 语义幻觉检测：时间错位（v3.0）
- [x] 语义幻觉检测：指标混淆（v3.0）
- [x] 语义幻觉检测：因果编造（v3.0）
- [x] 统一流水线：regex + LLM 双提取，数字 + 语义双核查（v3.0）
- [ ] 港股/美股数据源支持
- [ ] 更多指标（现金流、每股收益、分红等）
- [ ] Benchmark 评测集
- [ ] PyPI 发布

---

## License

MIT License — 详见 [LICENSE](LICENSE)

---

## 致谢

- [AKShare](https://github.com/akfamily/akshare) — 免费开源 A 股财经数据接口
- [SelfCheckGPT](https://arxiv.org/abs/2303.08896) — 自洽性幻觉检测思路参考
- [FacTool](https://arxiv.org/abs/2307.13528) — 事实核查思路参考

> AI生成