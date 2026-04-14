"""
价格趋势分析器 - 计算价格趋势指标
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from ..storage import Database
from ..logger import setup_logger


@dataclass
class TrendResult:
    """价格趋势分析结果"""
    product_id: int
    product_name: str
    platform: str
    current_price: float
    
    # 价格统计
    min_price: float
    max_price: float
    avg_price: float
    
    # 涨跌幅
    price_change: float = 0.0
    change_percent: float = 0.0
    
    # 波动范围
    volatility_range: float = 0.0
    volatility_percent: float = 0.0
    
    # 趋势方向
    trend_direction: str = "stable"  # up, down, stable
    
    # 分析周期
    days: int = 7
    record_count: int = 0
    
    # 价格历史
    price_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # 目标价格相关
    target_price: Optional[float] = None
    target_diff: float = 0.0
    target_diff_percent: float = 0.0


class TrendAnalyzer:
    """价格趋势分析器"""
    
    def __init__(self, db: Database = None):
        self.logger = setup_logger(self.__class__.__name__)
        self.db = db or Database()
    
    def analyze_product(self, product_id: int, days: int = 7) -> Optional[TrendResult]:
        """分析单个商品的价格趋势"""
        product = self.db.get_product(product_id)
        if not product:
            self.logger.warning(f"商品不存在: {product_id}")
            return None
        
        # 获取价格历史
        price_history = self.db.get_price_history(product_id, days=days)
        if not price_history:
            self.logger.warning(f"无价格历史: {product_id}")
            return None
        
        # 反转顺序，按时间正序排列
        price_history = list(reversed(price_history))
        
        # 计算统计数据
        prices = [h['price'] for h in price_history]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = statistics.mean(prices)
        current_price = prices[-1]
        
        # 计算涨跌幅
        first_price = prices[0]
        price_change = current_price - first_price
        change_percent = (price_change / first_price * 100) if first_price > 0 else 0
        
        # 确定趋势方向
        if change_percent > 2:
            trend_direction = "up"
        elif change_percent < -2:
            trend_direction = "down"
        else:
            trend_direction = "stable"
        
        # 计算波动范围
        volatility_range = max_price - min_price
        volatility_percent = (volatility_range / avg_price * 100) if avg_price > 0 else 0
        
        # 计算与目标价的差异
        target_price = product.get('target_price')
        target_diff = 0.0
        target_diff_percent = 0.0
        if target_price:
            target_diff = current_price - target_price
            target_diff_percent = (target_diff / target_price * 100) if target_price > 0 else 0
        
        return TrendResult(
            product_id=product_id,
            product_name=product['name'],
            platform=product['platform'],
            current_price=current_price,
            min_price=min_price,
            max_price=max_price,
            avg_price=avg_price,
            price_change=price_change,
            change_percent=change_percent,
            volatility_range=volatility_range,
            volatility_percent=volatility_percent,
            trend_direction=trend_direction,
            days=days,
            record_count=len(price_history),
            price_history=price_history,
            target_price=target_price,
            target_diff=target_diff,
            target_diff_percent=target_diff_percent
        )
    
    def analyze_all_products(self, days: int = 7) -> List[TrendResult]:
        """分析所有商品的价格趋势"""
        products = self.db.get_all_products()
        results = []
        
        for product in products:
            result = self.analyze_product(product['id'], days)
            if result:
                results.append(result)
        
        self.logger.info(f"完成 {len(results)} 个商品的趋势分析")
        return results
    
    def get_price_down_products(self, days: int = 7, min_percent: float = 0) -> List[TrendResult]:
        """获取降价商品列表"""
        results = self.analyze_all_products(days)
        down_products = [
            r for r in results 
            if r.change_percent < -min_percent
        ]
        return sorted(down_products, key=lambda x: x.change_percent)
    
    def get_price_up_products(self, days: int = 7, min_percent: float = 0) -> List[TrendResult]:
        """获取涨价商品列表"""
        results = self.analyze_all_products(days)
        up_products = [
            r for r in results 
            if r.change_percent > min_percent
        ]
        return sorted(up_products, key=lambda x: x.change_percent, reverse=True)
    
    def get_target_reached_products(self, days: int = 7) -> List[TrendResult]:
        """获取达到目标价格的商品"""
        results = self.analyze_all_products(days)
        reached_products = [
            r for r in results 
            if r.target_price and r.current_price <= r.target_price
        ]
        return reached_products
    
    def get_volatile_products(self, days: int = 7, min_volatility: float = 5.0) -> List[TrendResult]:
        """获取价格波动较大的商品"""
        results = self.analyze_all_products(days)
        volatile_products = [
            r for r in results 
            if r.volatility_percent >= min_volatility
        ]
        return sorted(volatile_products, key=lambda x: x.volatility_percent, reverse=True)
    
    def get_summary_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取汇总统计信息"""
        results = self.analyze_all_products(days)
        
        if not results:
            return {
                'total_products': 0,
                'price_down_count': 0,
                'price_up_count': 0,
                'stable_count': 0,
                'target_reached_count': 0,
                'avg_change_percent': 0
            }
        
        down_count = sum(1 for r in results if r.trend_direction == 'down')
        up_count = sum(1 for r in results if r.trend_direction == 'up')
        stable_count = sum(1 for r in results if r.trend_direction == 'stable')
        target_reached = sum(1 for r in results if r.target_price and r.current_price <= r.target_price)
        
        avg_change = statistics.mean([r.change_percent for r in results])
        
        return {
            'total_products': len(results),
            'price_down_count': down_count,
            'price_up_count': up_count,
            'stable_count': stable_count,
            'target_reached_count': target_reached,
            'avg_change_percent': avg_change,
            'analysis_period_days': days
        }
