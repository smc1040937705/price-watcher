import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import platform

import matplotlib
if platform.system() == 'Windows':
    font_list = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
else:
    font_list = ['PingFang SC', 'Hiragino Sans GB', 'Noto Sans CJK SC']
matplotlib.rcParams['font.sans-serif'] = font_list + ['DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.size'] = 10

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from ..storage import Database
from ..logger import setup_logger
from ..config import Config


@dataclass
class PriceTrend:
    product_id: int
    product_name: str
    platform: str
    url: str
    current_price: float
    start_price_7d: float
    start_price_30d: float
    min_price_7d: float
    min_price_30d: float
    max_price_7d: float
    max_price_30d: float
    avg_price_7d: float
    avg_price_30d: float
    price_change_7d: float
    price_change_30d: float
    price_change_percent_7d: float
    price_change_percent_30d: float
    volatility_7d: float
    volatility_30d: float
    lowest_price_date: str
    highest_price_date: str
    days_since_lowest: int
    days_since_highest: int
    current_position: str
    recommendation: str
    is_increasing_7d: bool
    is_decreasing_7d: bool
    is_increasing_30d: bool
    is_decreasing_30d: bool
    record_count: int


@dataclass
class ReportData:
    generated_at: str
    total_products: int
    products_with_history: int
    price_increase_count_7d: int
    price_decrease_count_7d: int
    price_increase_count_30d: int
    price_decrease_count_30d: int
    avg_price_change_7d: float
    avg_price_change_30d: float
    top_price_increases_7d: List[Dict[str, Any]]
    top_price_decreases_7d: List[Dict[str, Any]]
    top_price_increases_30d: List[Dict[str, Any]]
    top_price_decreases_30d: List[Dict[str, Any]]
    bargain_products: List[Dict[str, Any]]
    high_risk_products: List[Dict[str, Any]]
    all_trends: List[Dict[str, Any]]


class PriceAnalyzer:
    def __init__(self, db_path: str = None, json_path: str = None):
        self.db = Database(db_path)
        self.logger = setup_logger(self.__class__.__name__)
        self.config = Config()
        self.reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reports')
        os.makedirs(self.reports_dir, exist_ok=True)
        self.json_data = None
        if json_path and os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                self.json_data = json.load(f)
            self.logger.info(f"已加载JSON数据源: {json_path}, 包含 {len(self.json_data)} 个商品")

    def _get_price_history_from_json(self, product_db_id: int, days: int = None) -> List[Dict[str, Any]]:
        if not self.json_data:
            return []
        for p in self.json_data:
            if p['id'] == product_db_id:
                history = p.get('price_history', [])
                if days and history:
                    cutoff = datetime.now() - timedelta(days=days)
                    history = [h for h in history if datetime.strptime(h['recorded_at'], '%Y-%m-%d %H:%M:%S') >= cutoff]
                return history
        return []

    def _get_combined_price_history(self, product_db_id: int, days: int = None) -> List[Dict[str, Any]]:
        db_history = self.db.get_price_history(product_db_id, days)
        json_history = self._get_price_history_from_json(product_db_id, days)
        
        seen = set()
        combined = []
        for h in db_history + json_history:
            key = (h['recorded_at'], h['price'])
            if key not in seen:
                seen.add(key)
                combined.append(h)
        
        return sorted(combined, key=lambda x: x['recorded_at'])

    def calculate_trend(self, product_db_id: int) -> Optional[PriceTrend]:
        product = self.db.get_product(product_db_id)
        if not product:
            return None

        price_history_30d = self._get_combined_price_history(product_db_id, 30)
        price_history_7d = self._get_combined_price_history(product_db_id, 7)
        
        if len(price_history_30d) < 2:
            return None

        prices_30d = [p['price'] for p in price_history_30d]
        dates_30d = [datetime.strptime(p['recorded_at'], '%Y-%m-%d %H:%M:%S') for p in price_history_30d]
        
        current_price = prices_30d[-1]
        start_price_30d = prices_30d[0]
        min_price_30d = min(prices_30d)
        max_price_30d = max(prices_30d)
        avg_price_30d = sum(prices_30d) / len(prices_30d)
        
        min_idx_30d = prices_30d.index(min_price_30d)
        max_idx_30d = prices_30d.index(max_price_30d)
        lowest_price_date = dates_30d[min_idx_30d].strftime('%Y-%m-%d')
        highest_price_date = dates_30d[max_idx_30d].strftime('%Y-%m-%d')
        days_since_lowest = (datetime.now() - dates_30d[min_idx_30d]).days
        days_since_highest = (datetime.now() - dates_30d[max_idx_30d]).days

        price_change_30d = current_price - start_price_30d
        price_change_percent_30d = (price_change_30d / start_price_30d) * 100 if start_price_30d > 0 else 0
        
        price_std_30d = pd.Series(prices_30d).std()
        volatility_30d = (price_std_30d / avg_price_30d) * 100 if avg_price_30d > 0 else 0

        if len(price_history_7d) >= 2:
            prices_7d = [p['price'] for p in price_history_7d]
            start_price_7d = prices_7d[0]
            min_price_7d = min(prices_7d)
            max_price_7d = max(prices_7d)
            avg_price_7d = sum(prices_7d) / len(prices_7d)
            price_change_7d = current_price - start_price_7d
            price_change_percent_7d = (price_change_7d / start_price_7d) * 100 if start_price_7d > 0 else 0
            price_std_7d = pd.Series(prices_7d).std()
            volatility_7d = (price_std_7d / avg_price_7d) * 100 if avg_price_7d > 0 else 0
        else:
            start_price_7d = current_price
            min_price_7d = current_price
            max_price_7d = current_price
            avg_price_7d = current_price
            price_change_7d = 0
            price_change_percent_7d = 0
            volatility_7d = 0

        price_range = max_price_30d - min_price_30d
        if price_range > 0:
            position = ((current_price - min_price_30d) / price_range) * 100
        else:
            position = 50

        if position < 20:
            current_position = "历史低位区域"
        elif position < 40:
            current_position = "相对低位"
        elif position < 60:
            current_position = "中位区间"
        elif position < 80:
            current_position = "相对高位"
        else:
            current_position = "历史高位区域"

        if position < 25 and price_change_percent_30d < -5:
            recommendation = "强烈建议入手"
        elif position < 40 and price_change_percent_30d < 0:
            recommendation = "建议考虑"
        elif position > 75 and price_change_percent_30d > 5:
            recommendation = "建议观望"
        else:
            recommendation = "保持关注"

        return PriceTrend(
            product_id=product_db_id,
            product_name=product['name'],
            platform=product.get('platform', 'unknown'),
            url=product.get('url', ''),
            current_price=current_price,
            start_price_7d=start_price_7d,
            start_price_30d=start_price_30d,
            min_price_7d=min_price_7d,
            min_price_30d=min_price_30d,
            max_price_7d=max_price_7d,
            max_price_30d=max_price_30d,
            avg_price_7d=avg_price_7d,
            avg_price_30d=avg_price_30d,
            price_change_7d=price_change_7d,
            price_change_30d=price_change_30d,
            price_change_percent_7d=price_change_percent_7d,
            price_change_percent_30d=price_change_percent_30d,
            volatility_7d=volatility_7d,
            volatility_30d=volatility_30d,
            lowest_price_date=lowest_price_date,
            highest_price_date=highest_price_date,
            days_since_lowest=days_since_lowest,
            days_since_highest=days_since_highest,
            current_position=current_position,
            recommendation=recommendation,
            is_increasing_7d=price_change_percent_7d > 1,
            is_decreasing_7d=price_change_percent_7d < -1,
            is_increasing_30d=price_change_percent_30d > 1,
            is_decreasing_30d=price_change_percent_30d < -1,
            record_count=len(price_history_30d)
        )

    def analyze_all_products(self) -> ReportData:
        products = self.db.get_all_products()
        trends = []
        
        for product in products:
            trend = self.calculate_trend(product['id'])
            if trend:
                trends.append(trend)

        increase_count_7d = sum(1 for t in trends if t.is_increasing_7d)
        decrease_count_7d = sum(1 for t in trends if t.is_decreasing_7d)
        increase_count_30d = sum(1 for t in trends if t.is_increasing_30d)
        decrease_count_30d = sum(1 for t in trends if t.is_decreasing_30d)

        avg_change_7d = sum(t.price_change_percent_7d for t in trends) / len(trends) if trends else 0
        avg_change_30d = sum(t.price_change_percent_30d for t in trends) / len(trends) if trends else 0

        trends_sorted_increase_7d = sorted(trends, key=lambda x: x.price_change_percent_7d, reverse=True)
        trends_sorted_decrease_7d = sorted(trends, key=lambda x: x.price_change_percent_7d)
        trends_sorted_increase_30d = sorted(trends, key=lambda x: x.price_change_percent_30d, reverse=True)
        trends_sorted_decrease_30d = sorted(trends, key=lambda x: x.price_change_percent_30d)

        bargains = [t for t in trends if "建议入手" in t.recommendation or "建议考虑" in t.recommendation]
        high_risk = [t for t in trends if "建议观望" in t.recommendation]

        return ReportData(
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            total_products=len(products),
            products_with_history=len(trends),
            price_increase_count_7d=increase_count_7d,
            price_decrease_count_7d=decrease_count_7d,
            price_increase_count_30d=increase_count_30d,
            price_decrease_count_30d=decrease_count_30d,
            avg_price_change_7d=avg_change_7d,
            avg_price_change_30d=avg_change_30d,
            top_price_increases_7d=[asdict(t) for t in trends_sorted_increase_7d[:5] if t.is_increasing_7d],
            top_price_decreases_7d=[asdict(t) for t in trends_sorted_decrease_7d[:5] if t.is_decreasing_7d],
            top_price_increases_30d=[asdict(t) for t in trends_sorted_increase_30d[:5] if t.is_increasing_30d],
            top_price_decreases_30d=[asdict(t) for t in trends_sorted_decrease_30d[:5] if t.is_decreasing_30d],
            bargain_products=[asdict(t) for t in bargains],
            high_risk_products=[asdict(t) for t in high_risk],
            all_trends=[asdict(t) for t in trends]
        )

    def _generate_single_chart(self, product_db_id: int, days: int, product_name: str) -> str:
        price_history = self._get_combined_price_history(product_db_id, days)
        
        if len(price_history) < 2:
            return None

        price_history_sorted = sorted(price_history, key=lambda x: x['recorded_at'])
        dates = [datetime.strptime(p['recorded_at'], '%Y-%m-%d %H:%M:%S') for p in price_history_sorted]
        prices = [p['price'] for p in price_history_sorted]

        fig, ax = plt.subplots(figsize=(10, 5))
        
        ax.plot(dates, prices, marker='o', linewidth=2, markersize=5, color='#1f77b4', markeredgecolor='white')
        ax.fill_between(dates, prices, alpha=0.2, color='#1f77b4')

        ax.set_title(f'{product_name[:25]} - {days}天价格走势', fontsize=12, pad=15, fontweight='bold')
        ax.set_ylabel('价格 (元)', fontsize=10)
        ax.set_xlabel('', fontsize=9)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=0, fontsize=8)
        plt.yticks(fontsize=8)

        ax.grid(True, alpha=0.3)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        min_price = min(prices)
        max_price = max(prices)
        ax.set_ylim(min_price * 0.98, max_price * 1.02)

        annotations = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            if i == 0:
                annotations.append((date, price, f'起始\n{price:.0f}元', '#ff7f0e'))
            elif i == len(dates) - 1:
                annotations.append((date, price, f'当前\n{price:.0f}元', '#2ca02c'))
            elif price == min_price:
                annotations.append((date, price, f'最低\n{price:.0f}元', '#d62728'))
            elif price == max_price:
                annotations.append((date, price, f'最高\n{price:.0f}元', '#9467bd'))

        for date, price, text, color in annotations:
            ax.annotate(text, (date, price), textcoords="offset points",
                       xytext=(0, 10), ha='center', fontsize=7,
                       bbox=dict(boxstyle='round,pad=0.3', fc=color, alpha=0.8, ec='none'),
                       color='white', fontweight='bold')

        plt.tight_layout()
        output_path = os.path.join(self.reports_dir, f'product_{product_db_id}_{days}days.png')
        plt.savefig(output_path, dpi=120, bbox_inches='tight', facecolor='white')
        plt.close()
        return output_path

    def generate_dual_chart(self, product_db_id: int, output_path: str = None) -> str:
        product = self.db.get_product(product_db_id)
        if not product:
            return None

        chart_7d = self._generate_single_chart(product_db_id, 7, product['name'])
        chart_30d = self._generate_single_chart(product_db_id, 30, product['name'])
        
        return chart_30d

    def generate_all_charts(self) -> List[str]:
        products = self.db.get_all_products()
        chart_paths = []
        for product in products:
            chart_path = self.generate_dual_chart(product['id'])
            if chart_path:
                chart_paths.append(chart_path)
        return chart_paths

    def generate_markdown_report(self, output_path: str = None) -> str:
        report_data = self.analyze_all_products()

        md_content = f"""# 电商价格监控智能分析报告

> **全自动生成 | 综合7天与30天趋势分析**

---

### 📅 报告信息
| 项目 | 内容 |
|------|------|
| 🕒 生成时间 | {report_data.generated_at} |
| 📊 分析维度 | 7天短期 + 30天中期 |
| 📦 监控商品 | {report_data.total_products} 个 |
| 📈 有效分析 | {report_data.products_with_history} 个商品 |

---

## 1. 监控概览 Dashboard

### 1.1 价格变动统计

| 统计周期 | 🔺 涨价商品 | 🔻 降价商品 | ⚖️ 平均变动 |
|----------|-----------|-----------|-----------|
| **7天短期** | {report_data.price_increase_count_7d} 个 | {report_data.price_decrease_count_7d} 个 | {report_data.avg_price_change_7d:+.2f}% |
| **30天中期** | {report_data.price_increase_count_30d} 个 | {report_data.price_decrease_count_30d} 个 | {report_data.avg_price_change_30d:+.2f}% |

---

## 2. 降价商品清单

### 2.1 30天降价 TOP 5
"""

        if report_data.top_price_decreases_30d:
            md_content += """
| 商品名称 | 当前价格 | 30天降幅 | 7天变动 | 历史最低 | 距今天数 |
|----------|---------|---------|---------|---------|---------|
"""
            for item in report_data.top_price_decreases_30d:
                md_content += f"| {item['product_name'][:25]}... | ¥{item['current_price']:.0f} | **{item['price_change_percent_30d']:.1f}%** | {item['price_change_percent_7d']:+.1f}% | ¥{item['min_price_30d']:.0f} | {item['days_since_lowest']}天 |\n"
        else:
            md_content += "> 暂无显著降价商品\n"

        md_content += """
---

### 2.2 7天降价 TOP 5
"""

        if report_data.top_price_decreases_7d:
            md_content += """
| 商品名称 | 当前价格 | 7天降幅 | 最低价 | 推荐等级 |
|----------|---------|---------|--------|---------|
"""
            for item in report_data.top_price_decreases_7d:
                md_content += f"| {item['product_name'][:25]}... | ¥{item['current_price']:.0f} | **{item['price_change_percent_7d']:.1f}%** | ¥{item['min_price_7d']:.0f} | {item['recommendation']} |\n"
        else:
            md_content += "> 暂无短期显著降价商品\n"

        md_content += """
---

## 3. 涨价商品预警

### 3.1 30天涨价 TOP 5
"""

        if report_data.top_price_increases_30d:
            md_content += """
| 商品名称 | 当前价格 | 30天涨幅 | 7天变动 | 历史最高 | 距今天数 |
|----------|---------|---------|---------|---------|---------|
"""
            for item in report_data.top_price_increases_30d:
                md_content += f"| {item['product_name'][:25]}... | ¥{item['current_price']:.0f} | **+{item['price_change_percent_30d']:.1f}%** | {item['price_change_percent_7d']:+.1f}% | ¥{item['max_price_30d']:.0f} | {item['days_since_highest']}天 |\n"
        else:
            md_content += "> 暂无显著涨价商品\n"

        md_content += """
---

## 4. 🎯 智能推荐清单

### 4.1 推荐入手商品
"""

        if report_data.bargain_products:
            md_content += """
| 商品名称 | 当前价格 | 30天变动 | 当前位置 | 推荐指数 |
|----------|---------|---------|---------|---------|
"""
            for item in report_data.bargain_products:
                stars = "⭐⭐⭐⭐⭐" if "强烈建议" in item['recommendation'] else "⭐⭐⭐"
                md_content += f"| {item['product_name'][:25]}... | ¥{item['current_price']:.0f} | {item['price_change_percent_30d']:+.1f}% | {item['current_position']} | {stars} |\n"
        else:
            md_content += "> 当前暂无特别推荐入手的商品，保持关注！\n"

        md_content += """
---

### 4.2 建议观望商品
"""

        if report_data.high_risk_products:
            md_content += """
| 商品名称 | 当前价格 | 30天涨幅 | 当前位置 | 建议 |
|----------|---------|---------|---------|------|
"""
            for item in report_data.high_risk_products:
                md_content += f"| {item['product_name'][:25]}... | ¥{item['current_price']:.0f} | +{item['price_change_percent_30d']:.1f}% | {item['current_position']} | ⚠️ 高位谨慎 |\n"
        else:
            md_content += "> 当前无高风险商品\n"

        md_content += """
---

## 5. 🔍 重点商品深度分析

"""

        products = self.db.get_all_products()
        for product in products:
            trend = self.calculate_trend(product['id'])
            if trend:
                self.generate_dual_chart(product['id'])
                
                md_content += f"""
---

### 📦 {trend.product_name}

**平台**: {trend.platform.upper()} | **价格记录**: {trend.record_count} 条

#### 💰 价格指标
| 周期 | 当前价格 | 最低价 | 最高价 | 平均价 | 价格变动 | 波动率 |
|------|---------|-------|-------|-------|---------|-------|
| **7天** | ¥{trend.current_price:.0f} | ¥{trend.min_price_7d:.0f} | ¥{trend.max_price_7d:.0f} | ¥{trend.avg_price_7d:.0f} | {trend.price_change_percent_7d:+.1f}% | {trend.volatility_7d:.1f}% |
| **30天** | ¥{trend.current_price:.0f} | ¥{trend.min_price_30d:.0f} | ¥{trend.max_price_30d:.0f} | ¥{trend.avg_price_30d:.0f} | {trend.price_change_percent_30d:+.1f}% | {trend.volatility_30d:.1f}% |

#### 📊 趋势分析
- 🏆 **历史最低价**: ¥{trend.min_price_30d:.0f} ({trend.lowest_price_date}, {trend.days_since_lowest}天前)
- 📈 **历史最高价**: ¥{trend.max_price_30d:.0f} ({trend.highest_price_date}, {trend.days_since_highest}天前)
- 📍 **当前位置**: **{trend.current_position}**
- 💡 **智能建议**: **{trend.recommendation}**

#### 30天价格走势
![30天价格走势]({os.path.join(self.reports_dir, f'product_{product["id"]}_30days.png')})

#### 7天价格走势
![7天价格走势]({os.path.join(self.reports_dir, f'product_{product["id"]}_7days.png')})

"""

        if output_path is None:
            output_path = os.path.join(self.reports_dir, 'price_analysis_report.md')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        self.logger.info(f"Markdown报告已生成: {output_path}")
        return output_path

    def generate_excel_report(self, output_path: str = None) -> str:
        report_data = self.analyze_all_products()

        if output_path is None:
            output_path = os.path.join(self.reports_dir, 'price_analysis_report.xlsx')

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            overview_data = {
                '指标': ['监控商品总数', '有效分析商品', '7天涨价商品数', '7天降价商品数', '30天涨价商品数', '30天降价商品数', '7天平均变动', '30天平均变动', '生成时间'],
                '数值': [
                    report_data.total_products,
                    report_data.products_with_history,
                    report_data.price_increase_count_7d,
                    report_data.price_decrease_count_7d,
                    report_data.price_increase_count_30d,
                    report_data.price_decrease_count_30d,
                    f'{report_data.avg_price_change_7d:+.2f}%',
                    f'{report_data.avg_price_change_30d:+.2f}%',
                    report_data.generated_at
                ]
            }
            df_overview = pd.DataFrame(overview_data)
            df_overview.to_excel(writer, sheet_name='📊 监控概览', index=False)

            if report_data.top_price_decreases_30d:
                df = pd.DataFrame(report_data.top_price_decreases_30d)
                df = df[['product_name', 'current_price', 'min_price_30d', 'max_price_30d', 'price_change_percent_7d', 'price_change_percent_30d', 'current_position', 'recommendation']]
                df.columns = ['商品名称', '当前价格', '30天最低价', '30天最高价', '7天变动(%)', '30天降幅(%)', '当前位置', '推荐']
                df.to_excel(writer, sheet_name='📉 降价商品', index=False)

            if report_data.top_price_increases_30d:
                df = pd.DataFrame(report_data.top_price_increases_30d)
                df = df[['product_name', 'current_price', 'min_price_30d', 'max_price_30d', 'price_change_percent_7d', 'price_change_percent_30d', 'current_position']]
                df.columns = ['商品名称', '当前价格', '30天最低价', '30天最高价', '7天变动(%)', '30天涨幅(%)', '当前位置']
                df.to_excel(writer, sheet_name='📈 涨价商品', index=False)

            if report_data.bargain_products:
                df = pd.DataFrame(report_data.bargain_products)
                df = df[['product_name', 'platform', 'current_price', 'price_change_percent_30d', 'current_position', 'recommendation', 'url']]
                df.columns = ['商品名称', '平台', '当前价格', '30天变动(%)', '当前位置', '推荐等级', '链接']
                df.to_excel(writer, sheet_name='🎯 推荐商品', index=False)

            if report_data.all_trends:
                df = pd.DataFrame(report_data.all_trends)
                df = df[['product_name', 'platform', 'current_price', 'min_price_7d', 'max_price_7d', 'price_change_percent_7d', 'min_price_30d', 'max_price_30d', 'price_change_percent_30d', 'volatility_30d', 'current_position', 'recommendation', 'record_count']]
                df.columns = ['商品名称', '平台', '当前价格', '7天最低价', '7天最高价', '7天变动(%)', '30天最低价', '30天最高价', '30天变动(%)', '波动率(%)', '当前位置', '推荐', '记录数']
                df.to_excel(writer, sheet_name='📋 全部商品', index=False)

            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

        self.logger.info(f"Excel报告已生成: {output_path}")
        return output_path

    def generate_pdf_report(self, output_path: str = None) -> str:
        try:
            md_path = self.generate_markdown_report()
            
            if output_path is None:
                output_path = os.path.join(self.reports_dir, 'price_analysis_report.pdf')
            
            try:
                from xhtml2pdf import pisa
                import markdown2
                
                with open(md_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                
                html_content = markdown2.markdown(md_content, extras=['tables'])
                
                html_full = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{ font-family: 'Microsoft YaHei', 'SimHei', sans-serif; padding: 30px; line-height: 1.6; font-size: 12px; }}
                        h1 {{ color: #1f77b4; border-bottom: 3px solid #ff7f0e; padding-bottom: 10px; font-size: 20px; }}
                        h2 {{ color: #ff7f0e; margin-top: 25px; font-size: 16px; }}
                        h3 {{ color: #2ca02c; font-size: 14px; }}
                        h4 {{ color: #d62728; font-size: 13px; }}
                        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 10px; }}
                        th {{ background-color: #1f77b4; color: white; padding: 8px; }}
                        th, td {{ border: 1px solid #ddd; padding: 6px; text-align: left; }}
                        tr:nth-child(even) {{ background-color: #f8f9fa; }}
                        img {{ max-width: 100%; margin: 10px 0; }}
                        blockquote {{ background: #f0f8ff; border-left: 4px solid #1f77b4; padding: 10px; margin: 10px 0; }}
                    </style>
                    <base href="file:///{self.reports_dir.replace(os.sep, '/')}/">
                </head>
                <body>{html_content}</body>
                </html>
                """
                
                with open(output_path, 'wb') as f:
                    pisa_status = pisa.CreatePDF(html_full, dest=f)
                
                if not pisa_status.err:
                    self.logger.info(f"PDF报告已生成: {output_path}")
                    return output_path
                else:
                    raise Exception("xhtml2pdf 生成失败")
                    
            except Exception as e1:
                self.logger.warning(f"xhtml2pdf方案失败: {e1}，尝试备用方案...")
                
                try:
                    import subprocess
                    
                    html_path = os.path.join(self.reports_dir, 'temp_report.html')
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html_full if 'html_full' in locals() else open(md_path, encoding='utf-8').read())
                    
                    self.logger.info(f"已生成HTML文件: {html_path}")
                    self.logger.info("提示: 可使用浏览器打开HTML文件后手动打印为PDF")
                    
                    return None
                    
                except Exception as e2:
                    self.logger.error(f"PDF生成失败: {e2}")
                    self.logger.info("建议解决方案:")
                    self.logger.info("  1. 使用已生成的Markdown文件转换")
                    self.logger.info("  2. 或安装: pip install xhtml2pdf")
                    return None
                    
        except ImportError as e:
            self.logger.warning(f"PDF生成依赖未安装: {e}")
            self.logger.info("请执行: pip install xhtml2pdf markdown2")
            return None

    def generate_full_report(self, formats: List[str] = ['markdown', 'excel', 'pdf']) -> Dict[str, str]:
        results = {}
        self.generate_all_charts()

        if 'markdown' in formats:
            results['markdown'] = self.generate_markdown_report()
        if 'excel' in formats:
            results['excel'] = self.generate_excel_report()
        if 'pdf' in formats:
            results['pdf'] = self.generate_pdf_report()

        return results
