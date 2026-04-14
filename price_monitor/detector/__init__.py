from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
from ..storage import Database
from ..logger import setup_logger

class ChangeType(Enum):
    PRICE_DOWN = "price_down"
    PRICE_UP = "price_up"
    NO_CHANGE = "no_change"
    TARGET_REACHED = "target_reached"

@dataclass
class PriceChange:
    product_id: int
    product_name: str
    product_url: str
    old_price: float
    new_price: float
    change_type: ChangeType
    change_amount: float
    change_percent: float
    target_price: Optional[float] = None

class PriceChangeDetector:
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.db = Database()

    def detect_changes(self) -> List[PriceChange]:
        products = self.db.get_all_products()
        changes = []

        for product in products:
            change = self.detect_product_change(product['id'])
            if change:
                changes.append(change)

        return changes

    def detect_product_change(self, product_id: int) -> Optional[PriceChange]:
        price_history = self.db.get_price_history(product_id, days=7)
        
        if len(price_history) < 2:
            return None
        
        product = self.db.get_product(product_id)
        new_price = price_history[0]['price']
        old_price = price_history[1]['price']
        
        if new_price == old_price:
            return None
        
        change_amount = new_price - old_price
        change_percent = (change_amount / old_price) * 100 if old_price > 0 else 0
        
        if new_price < old_price:
            change_type = ChangeType.PRICE_DOWN
        else:
            change_type = ChangeType.PRICE_UP
        
        target_reached = False
        if product['target_price'] and new_price <= product['target_price']:
            change_type = ChangeType.TARGET_REACHED
            target_reached = True
        
        change = PriceChange(
            product_id=product_id,
            product_name=product['name'],
            product_url=product['url'],
            old_price=old_price,
            new_price=new_price,
            change_type=change_type,
            change_amount=abs(change_amount),
            change_percent=abs(change_percent),
            target_price=product['target_price']
        )
        
        if change_type == ChangeType.PRICE_DOWN:
            self.logger.info(f"降价检测: {product['name']} - ¥{old_price} → ¥{new_price}, 降了{change_percent:.1f}%")
        elif change_type == ChangeType.PRICE_UP:
            self.logger.info(f"涨价检测: {product['name']} - ¥{old_price} → ¥{new_price}, 涨了{change_percent:.1f}%")
        elif change_type == ChangeType.TARGET_REACHED:
            self.logger.info(f"达到目标价: {product['name']} - 现价¥{new_price}, 目标价¥{product['target_price']}")
        
        return change

    def get_bargains(self, min_discount_percent: float = 10.0) -> List[PriceChange]:
        changes = self.detect_changes()
        bargains = [
            c for c in changes 
            if c.change_type in [ChangeType.PRICE_DOWN, ChangeType.TARGET_REACHED] 
            and c.change_percent >= min_discount_percent
        ]
        return bargains

    def get_summary(self) -> Dict[str, Any]:
        products = self.db.get_all_products()
        changes = self.detect_changes()
        
        price_downs = [c for c in changes if c.change_type == ChangeType.PRICE_DOWN]
        price_ups = [c for c in changes if c.change_type == ChangeType.PRICE_UP]
        targets = [c for c in changes if c.change_type == ChangeType.TARGET_REACHED]
        
        return {
            'total_products': len(products),
            'total_changes': len(changes),
            'price_downs': len(price_downs),
            'price_ups': len(price_ups),
            'target_reached': len(targets),
            'changes': changes
        }
