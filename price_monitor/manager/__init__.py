from typing import List, Optional, Dict, Any
from ..spider import PriceSpider, ProductInfo
from ..storage import Database
from ..logger import setup_logger

class ProductManager:
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.spider = PriceSpider()
        self.db = Database()

    def add_product(self, url: str, target_price: float = None) -> Optional[Dict[str, Any]]:
        self.logger.info(f"添加商品: {url}")
        
        product_info = self.spider.crawl(url)
        if not product_info:
            self.logger.error("爬取商品信息失败")
            return None
        
        product_db_id = self.db.add_product(product_info, target_price)
        return self.db.get_product(product_db_id)

    def add_products_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        results = []
        for url in urls:
            result = self.add_product(url)
            if result:
                results.append(result)
        return results

    def remove_product(self, product_id: int) -> bool:
        return self.db.delete_product(product_id)

    def list_products(self) -> List[Dict[str, Any]]:
        products = self.db.get_all_products()
        for p in products:
            latest_price = self.db.get_latest_price(p['id'])
            if latest_price:
                p['current_price'] = latest_price['price']
                p['last_check'] = latest_price['recorded_at']
            
            stats = self.db.get_price_stats(p['id'])
            p['min_price'] = stats['min_price']
            p['max_price'] = stats['max_price']
            p['avg_price'] = stats['avg_price']
        
        return products

    def get_product_detail(self, product_id: int) -> Optional[Dict[str, Any]]:
        product = self.db.get_product(product_id)
        if not product:
            return None
        
        price_history = self.db.get_price_history(product_id)
        stats = self.db.get_price_stats(product_id)
        
        return {
            'product': product,
            'price_history': price_history,
            'stats': stats
        }

    def refresh_all(self) -> List[Dict[str, Any]]:
        products = self.db.get_all_products()
        self.logger.info(f"开始刷新 {len(products)} 个商品的价格")
        
        results = []
        for product in products:
            result = self.refresh_product(product['id'])
            if result:
                results.append(result)
        
        self.logger.info(f"刷新完成，成功更新 {len(results)} 个商品")
        return results

    def refresh_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        product = self.db.get_product(product_id)
        if not product:
            return None
        
        self.logger.info(f"刷新商品价格: {product['name']}")
        
        product_info = self.spider.crawl(product['url'])
        if not product_info:
            return None
        
        self.db.record_price(product_id, product_info)
        
        detail = self.get_product_detail(product_id)
        detail['product']['current_price'] = product_info.price
        
        return detail
