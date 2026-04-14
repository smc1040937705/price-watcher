import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

from .analyzer import ProductAnalysis
from ..logger import setup_logger

class PriceVisualizer:
    def __init__(self, output_dir: str = 'reports/charts'):
        self.logger = setup_logger(self.__class__.__name__)
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def _parse_datetime(self, date_str: str) -> datetime:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    
    def plot_price_trend(self, analysis: ProductAnalysis, days: int = 30, 
                         save_path: Optional[str] = None) -> str:
        fig, ax = plt.subplots(figsize=(12, 6))
        
        history = analysis.price_history
        if days:
            cutoff = datetime.now() - __import__('datetime').timedelta(days=days)
            history = [
                h for h in history 
                if self._parse_datetime(h['recorded_at']) >= cutoff
            ]
        
        if not history:
            ax.text(0.5, 0.5, '暂无价格数据', ha='center', va='center', fontsize=14)
            ax.set_title(f'{analysis.product_name[:30]} - 价格趋势')
            plt.tight_layout()
            
            if save_path is None:
                save_path = os.path.join(self.output_dir, f'product_{analysis.product_id}_trend.png')
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            return save_path
        
        dates = [self._parse_datetime(h['recorded_at']) for h in history]
        prices = [h['price'] for h in history]
        
        ax.plot(dates, prices, 'b-', linewidth=2, marker='o', markersize=4, label='价格')
        
        if analysis.target_price:
            ax.axhline(y=analysis.target_price, color='r', linestyle='--', 
                      linewidth=1.5, label=f'目标价: ¥{analysis.target_price:.2f}')
        
        if analysis.trend_all:
            ax.axhline(y=analysis.trend_all.avg_price, color='g', linestyle=':', 
                      linewidth=1.5, label=f'平均价: ¥{analysis.trend_all.avg_price:.2f}')
            
            min_price = analysis.trend_all.min_price
            max_price = analysis.trend_all.max_price
            ax.fill_between(dates, min_price, max_price, alpha=0.1, color='blue')
        
        ax.set_xlabel('日期', fontsize=11)
        ax.set_ylabel('价格 (元)', fontsize=11)
        ax.set_title(f'{analysis.product_name[:40]} - {days}天价格走势', fontsize=13)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45)
        
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        if prices:
            y_min = min(prices) * 0.95
            y_max = max(prices) * 1.05
            if analysis.target_price:
                y_min = min(y_min, analysis.target_price * 0.95)
                y_max = max(y_max, analysis.target_price * 1.05)
            ax.set_ylim(y_min, y_max)
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = os.path.join(self.output_dir, f'product_{analysis.product_id}_trend_{days}d.png')
        
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        self.logger.info(f"价格趋势图已保存: {save_path}")
        return save_path
    
    def plot_multi_product_comparison(self, analyses: List[ProductAnalysis], 
                                       days: int = 30, save_path: Optional[str] = None) -> str:
        fig, ax = plt.subplots(figsize=(14, 8))
        
        colors = plt.cm.tab10.colors
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']
        
        for idx, analysis in enumerate(analyses[:10]):
            history = analysis.price_history
            if days:
                cutoff = datetime.now() - __import__('datetime').timedelta(days=days)
                history = [
                    h for h in history 
                    if self._parse_datetime(h['recorded_at']) >= cutoff
                ]
            
            if not history:
                continue
            
            dates = [self._parse_datetime(h['recorded_at']) for h in history]
            prices = [h['price'] for h in history]
            
            color = colors[idx % len(colors)]
            marker = markers[idx % len(markers)]
            
            label = analysis.product_name[:20]
            ax.plot(dates, prices, color=color, linewidth=2, marker=marker, 
                   markersize=4, label=label)
        
        ax.set_xlabel('日期', fontsize=11)
        ax.set_ylabel('价格 (元)', fontsize=11)
        ax.set_title(f'商品价格对比 - {days}天走势', fontsize=13)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45)
        
        ax.legend(loc='best', fontsize=9, ncol=2)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'multi_product_comparison.png')
        
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        self.logger.info(f"多商品对比图已保存: {save_path}")
        return save_path
    
    def plot_price_change_distribution(self, analyses: List[ProductAnalysis], 
                                        save_path: Optional[str] = None) -> str:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        change_percents = [a.change_percent_recent for a in analyses if a.change_percent_recent != 0]
        
        if change_percents:
            colors = ['green' if x < 0 else 'red' for x in change_percents]
            bars = ax1.bar(range(len(change_percents)), change_percents, color=colors, alpha=0.7)
            ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax1.set_xlabel('商品序号', fontsize=11)
            ax1.set_ylabel('价格变动 (%)', fontsize=11)
            ax1.set_title('各商品价格变动幅度', fontsize=13)
            ax1.grid(True, alpha=0.3, axis='y')
        
        categories = ['降价', '涨价', '持平']
        down_count = sum(1 for a in analyses if a.change_percent_recent < -1)
        up_count = sum(1 for a in analyses if a.change_percent_recent > 1)
        stable_count = len(analyses) - down_count - up_count
        sizes = [down_count, up_count, stable_count]
        colors = ['#2ecc71', '#e74c3c', '#95a5a6']
        explode = (0.05, 0.05, 0)
        
        if any(sizes):
            wedges, texts, autotexts = ax2.pie(sizes, explode=explode, labels=categories, 
                                                colors=colors, autopct='%1.1f%%',
                                                shadow=True, startangle=90)
            ax2.set_title('价格变动分布', fontsize=13)
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'price_change_distribution.png')
        
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        self.logger.info(f"价格变动分布图已保存: {save_path}")
        return save_path
    
    def plot_volatility_ranking(self, analyses: List[ProductAnalysis], 
                                 top_n: int = 10, save_path: Optional[str] = None) -> str:
        sorted_analyses = sorted(analyses, key=lambda x: x.trend_all.volatility, reverse=True)[:top_n]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        names = [a.product_name[:15] + '...' if len(a.product_name) > 15 
                 else a.product_name for a in sorted_analyses]
        volatilities = [a.trend_all.volatility for a in sorted_analyses]
        
        colors = plt.cm.RdYlGn_r([v / max(volatilities) if volatilities else 0 for v in volatilities])
        
        bars = ax.barh(range(len(names)), volatilities, color=colors, alpha=0.8)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=9)
        ax.set_xlabel('波动率 (%)', fontsize=11)
        ax.set_title(f'价格波动率 TOP {top_n}', fontsize=13)
        ax.grid(True, alpha=0.3, axis='x')
        
        for i, (bar, vol) in enumerate(zip(bars, volatilities)):
            ax.text(vol + 0.1, i, f'{vol:.1f}%', va='center', fontsize=9)
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'volatility_ranking.png')
        
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        self.logger.info(f"波动率排名图已保存: {save_path}")
        return save_path
    
    def generate_all_charts(self, analyses: List[ProductAnalysis], 
                            top_products: List[ProductAnalysis] = None) -> Dict[str, str]:
        charts = {}
        
        if top_products is None:
            top_products = analyses[:5]
        
        if analyses:
            charts['distribution'] = self.plot_price_change_distribution(analyses)
            charts['volatility'] = self.plot_volatility_ranking(analyses)
        
        if top_products:
            charts['comparison'] = self.plot_multi_product_comparison(top_products)
        
        for analysis in top_products[:3]:
            chart_path = self.plot_price_trend(analysis, days=30)
            charts[f'product_{analysis.product_id}'] = chart_path
        
        return charts
