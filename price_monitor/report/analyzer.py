import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from ..storage import Database
from ..logger import setup_logger

@dataclass
class PriceTrend:
    min_price: float
    max_price: float
    avg_price: float
    current_price: float
    price_range: float
    volatility: float
    trend_direction: str
    change_percent: float
    lowest_date: Optional[str] = None
    highest_date: Optional[str] = None
    record_count: int = 0

@dataclass
class DataSourceInfo:
    source_type: str
    product_count: int
    last_updated: Optional[str] = None
    has_conflict: bool = False
    conflict_details: List[str] = field(default_factory=list)

@dataclass
class ProductAnalysis:
    product_id: int
    product_name: str
    platform: str
    url: str
    target_price: Optional[float]
    current_price: float
    trend_7d: Optional[PriceTrend]
    trend_30d: Optional[PriceTrend]
    trend_all: PriceTrend
    price_history: List[Dict[str, Any]]
    is_bargain: bool = False
    is_price_up: bool = False
    reached_target: bool = False
    change_amount: float = 0.0
    change_percent_recent: float = 0.0
    data_source: str = "database"

class PriceAnalyzer:
    def __init__(self, db_path: str = None, json_path: str = None):
        self.logger = setup_logger(self.__class__.__name__)
        self.db_path = db_path
        self.json_path = json_path
        self.db = None
        self._json_data = None
        self._db_data = None
        self._data_source_info: Optional[DataSourceInfo] = None
        
        if db_path or True:
            self.db = Database(db_path)
    
    def _load_json_data(self) -> List[Dict[str, Any]]:
        if self._json_data is None and self.json_path:
            if os.path.exists(self.json_path):
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    self._json_data = json.load(f)
                self.logger.info(f"已加载JSON数据: {self.json_path}")
            else:
                self.logger.warning(f"JSON文件不存在: {self.json_path}")
        return self._json_data or []
    
    def _load_db_data(self) -> List[Dict[str, Any]]:
        if self._db_data is None and self.db:
            products = self.db.get_all_products(enabled_only=False)
            self._db_data = []
            for product in products:
                history = self.db.get_price_history(product['id'])
                product_copy = dict(product)
                product_copy['price_history'] = history
                self._db_data.append(product_copy)
            self.logger.info(f"已加载数据库数据: {len(self._db_data)} 个商品")
        return self._db_data or []
    
    def validate_data_sources(self) -> DataSourceInfo:
        json_data = self._load_json_data()
        db_data = self._load_db_data()
        
        conflicts = []
        has_conflict = False
        
        if json_data and db_data:
            json_products = {p['id']: p for p in json_data}
            db_products = {p['id']: p for p in db_data}
            
            json_ids = set(json_products.keys())
            db_ids = set(db_products.keys())
            
            only_in_json = json_ids - db_ids
            only_in_db = db_ids - json_ids
            
            if only_in_json:
                conflicts.append(f"JSON中存在但数据库中不存在的商品ID: {only_in_json}")
                has_conflict = True
            
            if only_in_db:
                conflicts.append(f"数据库中存在但JSON中不存在的商品ID: {only_in_db}")
                has_conflict = True
            
            common_ids = json_ids & db_ids
            for pid in common_ids:
                json_p = json_products[pid]
                db_p = db_products[pid]
                
                json_history_count = len(json_p.get('price_history', []))
                db_history_count = len(db_p.get('price_history', []))
                
                if json_history_count != db_history_count:
                    conflicts.append(
                        f"商品ID {pid} ({json_p.get('name', 'Unknown')}) "
                        f"价格记录数不一致: JSON={json_history_count}, DB={db_history_count}"
                    )
                    has_conflict = True
                
                if json_p.get('target_price') != db_p.get('target_price'):
                    conflicts.append(
                        f"商品ID {pid} 目标价格不一致: "
                        f"JSON={json_p.get('target_price')}, DB={db_p.get('target_price')}"
                    )
                    has_conflict = True
        
        if json_data and db_data:
            source_type = "both"
            product_count = max(len(json_data), len(db_data))
        elif json_data:
            source_type = "json"
            product_count = len(json_data)
        elif db_data:
            source_type = "database"
            product_count = len(db_data)
        else:
            source_type = "none"
            product_count = 0
        
        last_updated = None
        if db_data:
            for p in db_data:
                if p.get('updated_at'):
                    if last_updated is None or p['updated_at'] > last_updated:
                        last_updated = p['updated_at']
        
        self._data_source_info = DataSourceInfo(
            source_type=source_type,
            product_count=product_count,
            last_updated=last_updated,
            has_conflict=has_conflict,
            conflict_details=conflicts
        )
        
        if has_conflict:
            self.logger.warning(f"数据源存在冲突，共 {len(conflicts)} 个问题")
            for conflict in conflicts:
                self.logger.warning(f"  - {conflict}")
        
        return self._data_source_info
    
    def get_data_source_info(self) -> Optional[DataSourceInfo]:
        return self._data_source_info
    
    def calculate_trend(self, price_history: List[Dict[str, Any]], days: int = None) -> Optional[PriceTrend]:
        if not price_history:
            return None
        
        prices = [h['price'] for h in price_history]
        
        if len(prices) < 1:
            return None
        
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        current_price = prices[-1]
        first_price = prices[0]
        
        price_range = max_price - min_price
        
        if avg_price > 0:
            variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
            volatility = (variance ** 0.5) / avg_price * 100
        else:
            volatility = 0
        
        if len(prices) >= 2:
            if current_price > first_price:
                trend_direction = "上涨"
            elif current_price < first_price:
                trend_direction = "下跌"
            else:
                trend_direction = "持平"
            
            if first_price > 0:
                change_percent = (current_price - first_price) / first_price * 100
            else:
                change_percent = 0
        else:
            trend_direction = "数据不足"
            change_percent = 0
        
        lowest_date = None
        highest_date = None
        for h in price_history:
            if h['price'] == min_price and lowest_date is None:
                lowest_date = h['recorded_at']
            if h['price'] == max_price and highest_date is None:
                highest_date = h['recorded_at']
        
        return PriceTrend(
            min_price=min_price,
            max_price=max_price,
            avg_price=avg_price,
            current_price=current_price,
            price_range=price_range,
            volatility=volatility,
            trend_direction=trend_direction,
            change_percent=change_percent,
            lowest_date=lowest_date,
            highest_date=highest_date,
            record_count=len(prices)
        )
    
    def analyze_product(self, product: Dict[str, Any], price_history: List[Dict[str, Any]], 
                        data_source: str = "database") -> ProductAnalysis:
        now = datetime.now()
        
        def filter_by_days(history: List[Dict], days: int) -> List[Dict]:
            cutoff = now - timedelta(days=days)
            return [
                h for h in history 
                if datetime.strptime(h['recorded_at'], '%Y-%m-%d %H:%M:%S') >= cutoff
            ]
        
        history_7d = filter_by_days(price_history, 7)
        history_30d = filter_by_days(price_history, 30)
        
        sorted_history = sorted(price_history, key=lambda x: x['recorded_at'])
        
        trend_7d = self.calculate_trend(history_7d, 7) if history_7d else None
        trend_30d = self.calculate_trend(history_30d, 30) if history_30d else None
        trend_all = self.calculate_trend(sorted_history)
        
        current_price = sorted_history[-1]['price'] if sorted_history else 0
        
        is_bargain = False
        is_price_up = False
        change_amount = 0.0
        change_percent_recent = 0.0
        
        if len(sorted_history) >= 2:
            prev_price = sorted_history[-2]['price']
            change_amount = current_price - prev_price
            if prev_price > 0:
                change_percent_recent = (current_price - prev_price) / prev_price * 100
            
            if change_percent_recent < -5:
                is_bargain = True
            elif change_percent_recent > 5:
                is_price_up = True
        
        target_price = product.get('target_price')
        reached_target = target_price and current_price <= target_price
        
        return ProductAnalysis(
            product_id=product['id'],
            product_name=product['name'],
            platform=product['platform'],
            url=product['url'],
            target_price=target_price,
            current_price=current_price,
            trend_7d=trend_7d,
            trend_30d=trend_30d,
            trend_all=trend_all,
            price_history=sorted_history,
            is_bargain=is_bargain,
            is_price_up=is_price_up,
            reached_target=reached_target,
            change_amount=change_amount,
            change_percent_recent=change_percent_recent,
            data_source=data_source
        )
    
    def analyze_all_from_db(self) -> List[ProductAnalysis]:
        db_data = self._load_db_data()
        analyses = []
        
        for product in db_data:
            history = product.get('price_history', [])
            if history:
                analysis = self.analyze_product(product, history, data_source="database")
                analyses.append(analysis)
        
        return analyses
    
    def analyze_all_from_json(self) -> List[ProductAnalysis]:
        json_data = self._load_json_data()
        analyses = []
        
        for product in json_data:
            history = product.get('price_history', [])
            if history:
                analysis = self.analyze_product(product, history, data_source="json")
                analyses.append(analysis)
        
        return analyses
    
    def analyze_all(self, use_json: bool = False, prefer_source: str = "auto") -> List[ProductAnalysis]:
        if prefer_source == "auto":
            source_info = self.validate_data_sources()
            
            if source_info.has_conflict:
                self.logger.warning(
                    f"检测到数据源冲突，将使用数据库数据作为主数据源。"
                    f"冲突详情: {'; '.join(source_info.conflict_details[:3])}"
                    + ("..." if len(source_info.conflict_details) > 3 else "")
                )
            
            if use_json and self.json_path:
                return self.analyze_all_from_json()
            return self.analyze_all_from_db()
        
        elif prefer_source == "json" or use_json:
            if self.json_path:
                return self.analyze_all_from_json()
            else:
                self.logger.warning("未指定JSON路径，回退使用数据库数据")
                return self.analyze_all_from_db()
        
        elif prefer_source == "database":
            return self.analyze_all_from_db()
        
        elif prefer_source == "merge":
            return self._analyze_merged_data()
        
        return self.analyze_all_from_db()
    
    def _analyze_merged_data(self) -> List[ProductAnalysis]:
        json_data = self._load_json_data()
        db_data = self._load_db_data()
        
        merged = {}
        
        for product in db_data:
            pid = product['id']
            merged[pid] = product
            merged[pid]['data_source'] = 'database'
        
        for product in json_data:
            pid = product['id']
            if pid not in merged:
                merged[pid] = product
                merged[pid]['data_source'] = 'json'
            else:
                db_history = merged[pid].get('price_history', [])
                json_history = product.get('price_history', [])
                
                all_records = {h['recorded_at']: h for h in db_history}
                for h in json_history:
                    if h['recorded_at'] not in all_records:
                        all_records[h['recorded_at']] = h
                
                merged[pid]['price_history'] = list(all_records.values())
                merged[pid]['data_source'] = 'merged'
        
        analyses = []
        for product in merged.values():
            history = product.get('price_history', [])
            if history:
                analysis = self.analyze_product(
                    product, history, 
                    data_source=product.get('data_source', 'merged')
                )
                analyses.append(analysis)
        
        self.logger.info(f"合并数据源完成，共 {len(analyses)} 个商品")
        return analyses
    
    def get_summary(self, analyses: List[ProductAnalysis]) -> Dict[str, Any]:
        if not analyses:
            return {
                'total_products': 0,
                'total_price_down': 0,
                'total_price_up': 0,
                'total_target_reached': 0,
                'avg_change_percent': 0.0,
                'bargain_count': 0,
                'price_up_count': 0,
                'data_source_info': None
            }
        
        total_price_down = sum(1 for a in analyses if a.change_percent_recent < 0)
        total_price_up = sum(1 for a in analyses if a.change_percent_recent > 0)
        total_target_reached = sum(1 for a in analyses if a.reached_target)
        bargain_count = sum(1 for a in analyses if a.is_bargain)
        price_up_count = sum(1 for a in analyses if a.is_price_up)
        
        avg_change = sum(a.change_percent_recent for a in analyses) / len(analyses)
        
        return {
            'total_products': len(analyses),
            'total_price_down': total_price_down,
            'total_price_up': total_price_up,
            'total_target_reached': total_target_reached,
            'avg_change_percent': round(avg_change, 2),
            'bargain_count': bargain_count,
            'price_up_count': price_up_count,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source_info': self._data_source_info
        }
    
    def get_bargain_products(self, analyses: List[ProductAnalysis], threshold: float = -5.0) -> List[ProductAnalysis]:
        return [a for a in analyses if a.change_percent_recent <= threshold]
    
    def get_price_up_products(self, analyses: List[ProductAnalysis], threshold: float = 5.0) -> List[ProductAnalysis]:
        return [a for a in analyses if a.change_percent_recent >= threshold]
    
    def get_top_volatile_products(self, analyses: List[ProductAnalysis], top_n: int = 5) -> List[ProductAnalysis]:
        sorted_analyses = sorted(analyses, key=lambda x: x.trend_all.volatility, reverse=True)
        return sorted_analyses[:top_n]
    
    def get_target_reached_products(self, analyses: List[ProductAnalysis]) -> List[ProductAnalysis]:
        return [a for a in analyses if a.reached_target]
