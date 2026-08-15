---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '395f677c-f87e-4186-b5a0-5d36b432ed8a'
  PropagateID: '395f677c-f87e-4186-b5a0-5d36b432ed8a'
  ReservedCode1: '100b4a61-6f64-468d-a5a5-8adb18ba1276'
  ReservedCode2: '100b4a61-6f64-468d-a5a5-8adb18ba1276'
---

# antihall

**中文金融报告幻觉检测工具包** — 检测 LLM 生成的中文金融文本中的数字幻觉，通过对接真实 A 股财报数据进行验证，输出可解释的检测结果。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 为什么需要 antihall？

大语言模型（LLM）在生成金融分析、投研报告时，经常会**编造数字**——把营收、利润、增长率写错，而且错得"看起来很真实"。这在金融场景下是致命的：一个错误的数字可能导致错误的投资决策。

现有幻觉检测工具（SelfCheckGPT、FacTool 等）几乎全部面向英文、通用场景。**中文金融领域没有可用的开源幻觉检测工具。**

antihall 填补这个空白：

| 特性 | antihall | 通用幻觉检测工具 |
|------|----------|-----------------|
| 中文支持 | 原生中文 | 需要翻译/适配 |
| 数据源 | A 股真实财报（AKShare） | Wikipedia/英文知识库 |
| 检测类型 | 精确数字核查 | 语义自洽性（模糊） |
| 输出 | 哪句错、为什么、怎么改、证据链接 | 一个幻觉概率分数 |
| 适用场景 | 金融报告/投研分析 | 通用文本 |

---

## 核心功能

1. **声明提取**：从中文金融文本中自动提取"公司+指标+数值+年份"结构化声明
2. **真实数据核查**：通过 AKShare 对接 A 股公开财报，获取真实数值进行比对
3. **可解释判定**：不只给出"幻觉/正确"标签，还告诉你——
   - 哪句话有问题
   - 真实数据是多少
   - 偏差多大
   - 证据链接（可点击验证）
   - 修改建议（直接给出正确文本）
4. **HTML 可视化报告**：生成带高亮标注的检测报告，问题句子红色标记

---

## 安装

```bash
git clone https://github.com/xueshulqy770323/antihall.git
cd antihall
pip install -e .
pip install akshare  # 数据源依赖
```

---

## 快速开始

### 三行代码检测幻觉

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

```
输入文本
  │
  ▼
┌──────────────────┐
│  声明提取器        │  正则 + 规则引擎
│  (ClaimExtractor) │  提取：公司名 + 指标 + 数值 + 单位 + 年份
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  数据源            │  AKShare → A 股财报
│  (AKShareSource)  │  查询：真实数值 + 证据链接
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  核查引擎          │  单位换算 → 偏差计算 → 阈值判定
│  (NumericVerifier)│  判定：正确 / 幻觉 / 无法验证
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  解释器            │  生成：人话解释 + 修改建议 + 证据链接
│  (Explainer)      │
└────────┬─────────┘
         │
         ▼
   CheckResult
   (summary + 逐条详情 + HTML报告)
```

### 容差设定

不同指标允许的偏差范围不同：

| 指标类型 | 容差 | 原因 |
|---------|------|------|
| 营收/净利润 | 2% | 四舍五入和小数位差异 |
| 毛利率/净利率 | 1个百分点 | 比率类指标 |
| 同比增长率 | 5个百分点 | 计算基数可能不同 |

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
│   ├── __init__.py              # 包入口
│   ├── core.py                  # 主接口 HallucinationChecker
│   ├── models.py                # 核心数据结构
│   ├── extractor/
│   │   └── claim_extractor.py   # 金融声明提取（正则引擎）
│   ├── datasource/
│   │   └── akshare_source.py    # AKShare A 股财报数据源
│   ├── verifier/
│   │   └── numeric_verifier.py  # 数字核查引擎
│   ├── explainer/
│   │   └── explainer.py         # 解释器（人话+建议+证据）
│   └── report/
│       └── html_report.py       # HTML 可视化报告
├── tests/
│   ├── test_extractor.py        # 声明提取测试
│   ├── test_verifier.py         # 核查引擎测试
│   ├── test_explainer.py        # 解释器测试
│   └── test_html_report.py      # HTML 报告测试
├── examples/
│   ├── basic_usage.py           # 基本用法
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

---

## 路线图

- [x] 正则引擎提取金融声明
- [x] AKShare 对接 A 股财报
- [x] 数字核查 + 容差判定
- [x] 可解释输出（解释+建议+证据链接）
- [x] HTML 可视化报告
- [ ] LLM 辅助声明提取（更精准的语义理解）
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
