"""AKShare 数据源 — 通过 AKShare 开源库获取真实 A 股财报数据。

AKShare 是一个免费开源的 Python 财经数据接口库，
覆盖 A 股上市公司财报、行情、宏观经济等数据。
文档: https://akshare.akfamily.xyz/

本模块负责:
1. 将用户提到的公司名映射到股票代码
2. 拉取指定年份的财报指标
3. 返回标准化的 Evidence 对象
"""
from __future__ import annotations

import logging
from typing import Optional

from antihall.models import Evidence

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# 常见 A 股公司名 → 股票代码映射（内置常用，不全的靠 AKShare 模糊搜索）
# --------------------------------------------------------------------------- #
COMPANY_CODE_MAP: dict[str, str] = {
    "贵州茅台": "600519",
    "比亚迪": "002594",
    "宁德时代": "300750",
    "中国平安": "601318",
    "招商银行": "600036",
    "五粮液": "000858",
    "隆基绿能": "601012",
    "隆基股份": "601012",
    "美的集团": "000333",
    "格力电器": "000651",
    "海尔智家": "600690",
    "中国石油": "601857",
    "中国石化": "600028",
    "工商银行": "601398",
    "农业银行": "601288",
    "建设银行": "601939",
    "中国银行": "601988",
    "腾讯控股": "00700",  # 港股
    "阿里巴巴": "09988",  # 港股
    "京东方": "000725",
    "京东方A": "000725",
    "万科": "000002",
    "万科A": "000002",
    "恒瑞医药": "600276",
    "药明康德": "603259",
    "海康威视": "002415",
    "中芯国际": "688981",
    "长江电力": "600900",
    "中国中免": "601888",
    "三一重工": "600031",
    "福耀玻璃": "600660",
}

# AKShare 财报指标 → 我们内部 metric 名的映射
# AKShare stock_financial_abstract 返回的列名是中文
AKSHARE_METRIC_MAP: dict[str, list[str]] = {
    "营收": ["营业收入", "营业总收入"],
    "净利润": ["净利润", "归属母公司股东的净利润"],
    "归母净利润": ["归属母公司股东的净利润", "净利润"],
    "扣非净利润": ["扣除非经常性损益后的净利润"],
    "毛利率": ["销售毛利率", "毛利率"],
    "净利率": ["销售净利率", "净利率"],
    "资产负债率": ["资产负债率"],
    # ROE / 增长率 需要二次计算
}


class AKShareDataSource:
    """通过 AKShare 获取 A 股财报数据。"""

    def __init__(self):
        self._ak = None
        self._init_akshare()

    def _init_akshare(self):
        """延迟导入 akshare，避免未安装时报错。"""
        try:
            import akshare as ak
            self._ak = ak
        except ImportError:
            logger.warning(
                "akshare 未安装，请运行: pip install akshare"
            )
            self._ak = None

    @property
    def is_available(self) -> bool:
        return self._ak is not None

    def get_evidence(
        self,
        entity: str,
        metric: str,
        year: Optional[int] = None,
    ) -> Optional[Evidence]:
        """查询真实财报数据，返回 Evidence。

        Args:
            entity: 公司名（如"贵州茅台"）
            metric: 标准化指标名（如"营收"、"净利润"）
            year: 年份

        Returns:
            Evidence 对象，查询失败返回 None
        """
        if not self.is_available:
            return None

        stock_code = self._resolve_stock_code(entity)
        if not stock_code:
            logger.warning(f"无法找到公司 '{entity}' 的股票代码")
            return None

        try:
            return self._fetch_financial_data(stock_code, entity, metric, year)
        except Exception as e:
            logger.error(f"查询财报数据失败: {entity}/{metric}/{year}, 错误: {e}")
            return None

    def _resolve_stock_code(self, entity: str) -> str:
        """公司名 → 股票代码。"""
        # 1. 精确匹配
        if entity in COMPANY_CODE_MAP:
            return COMPANY_CODE_MAP[entity]

        # 2. 模糊匹配（去掉"有限公司"等后缀）
        for name, code in COMPANY_CODE_MAP.items():
            if entity in name or name in entity:
                return code

        # 3. 通过 AKShare 搜索（如果可用）
        if self.is_available:
            try:
                df = self._ak.stock_zh_a_spot_em()
                match = df[df["名称"].str.contains(entity)]
                if not match.empty:
                    code = match.iloc[0]["代码"]
                    logger.info(f"模糊匹配: '{entity}' -> {code}")
                    return code
            except Exception as e:
                logger.debug(f"AKShare 搜索失败: {e}")

        return ""

    def _fetch_financial_data(
        self,
        stock_code: str,
        entity: str,
        metric: str,
        year: Optional[int],
    ) -> Optional[Evidence]:
        """拉取财报摘要数据。"""
        ak_metric_names = AKSHARE_METRIC_MAP.get(metric, [metric])

        # AKShare: stock_financial_abstract 返回财务摘要
        df = self._ak.stock_financial_abstract(symbol=stock_code)

        if df is None or df.empty:
            logger.warning(f"AKShare 未返回数据: {stock_code}")
            return None

        # 找到匹配的列名
        col_name = None
        for candidate in ak_metric_names:
            if candidate in df.columns:
                col_name = candidate
                break

        if col_name is None:
            logger.warning(f"指标 '{metric}' 在 AKShare 数据中未找到匹配列")
            return None

        # 找到匹配年份的行
        target_row = self._find_year_row(df, year)

        if target_row is None:
            logger.warning(f"未找到 {year} 年的数据")
            return None

        actual_value = target_row[col_name]
        actual_value = self._safe_float(actual_value)
        if actual_value is None:
            return None

        # 构造证据链接（东方财富网个股页面）
        url = f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code={stock_code}"

        return Evidence(
            source_name="AKShare-年报",
            entity=entity,
            metric=metric,
            actual_value=actual_value,
            unit=self._guess_unit(metric),
            year=year,
            url=url,
            raw_data={
                "stock_code": stock_code,
                "ak_column": col_name,
                "ak_value": str(target_row[col_name]),
            },
        )

    def _find_year_row(self, df, year: Optional[int]):
        """在 DataFrame 中找到对应年份的行。"""
        if year is None:
            # 取最新一期
            return df.iloc[0]

        # 日期列可能叫 "选项" / "日期" / "报告日期"
        date_col = None
        for col in df.columns:
            if "日期" in col or "选项" in col or "报告" in col:
                date_col = col
                break

        if date_col is None:
            # 没有日期列，取第一行
            return df.iloc[0]

        for _, row in df.iterrows():
            date_str = str(row[date_col])
            if str(year) in date_str:
                return row

        return None

    def _guess_unit(self, metric: str) -> str:
        """根据指标推测单位。"""
        if metric in ("营收", "净利润", "归母净利润", "扣非净利润"):
            return "亿元"
        if metric in ("毛利率", "净利率", "资产负债率", "ROE", "同比增长率"):
            return "%"
        return ""

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """安全转 float。"""
        try:
            if isinstance(value, str):
                # 去除逗号、空格
                value = value.replace(",", "").strip()
                if "-" in value and value.replace("-", "").replace(".", "").isdigit():
                    return float(value)
            return float(value)
        except (ValueError, TypeError):
            return None
