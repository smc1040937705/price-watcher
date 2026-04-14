import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from dataclasses import asdict
from ..config import Config
from ..logger import setup_logger
from ..spider import ProductInfo

class Database:
    def __init__(self, db_path: str = None):
        self.config = Config()
        self.logger = setup_logger(self.__class__.__name__)
        
        if db_path is None:
            db_path = self.config.get('database.path', 'data/price_monitor.db')
        
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), db_path)
        
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            conn.close()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    platform TEXT NOT NULL,
                    product_id TEXT,
                    name TEXT NOT NULL,
                    target_price REAL,
                    image_url TEXT,
                    category TEXT,
                    is_enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    original_price REAL,
                    stock TEXT,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_price_history_product_id 
                ON price_history(product_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_price_history_recorded_at 
                ON price_history(recorded_at)
            ''')
            
            self.logger.info("数据库初始化完成")

    def add_product(self, product: ProductInfo, target_price: float = None) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM products WHERE url = ?', (product.url,))
            existing = cursor.fetchone()
            
            if existing:
                self.logger.warning(f"商品已存在: {product.url}")
                return existing['id']
            
            cursor.execute('''
                INSERT INTO products 
                (url, platform, product_id, name, image_url, category, target_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                product.url,
                product.platform,
                product.product_id,
                product.name,
                product.image_url,
                product.category,
                target_price
            ))
            
            product_db_id = cursor.lastrowid
            
            cursor.execute('''
                INSERT INTO price_history (product_id, price, original_price, stock)
                VALUES (?, ?, ?, ?)
            ''', (product_db_id, product.price, product.original_price, product.stock))
            
            self.logger.info(f"添加商品成功: {product.name}, ID: {product_db_id}")
            return product_db_id

    def record_price(self, product_db_id: int, product: ProductInfo):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO price_history (product_id, price, original_price, stock)
                VALUES (?, ?, ?, ?)
            ''', (product_db_id, product.price, product.original_price, product.stock))
            
            cursor.execute('''
                UPDATE products SET updated_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (product_db_id,))

    def get_product(self, product_db_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products WHERE id = ?', (product_db_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_product_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products WHERE url = ?', (url,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_products(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if enabled_only:
                cursor.execute('SELECT * FROM products WHERE is_enabled = 1 ORDER BY created_at DESC')
            else:
                cursor.execute('SELECT * FROM products ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]

    def get_price_history(self, product_db_id: int, days: int = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if days:
                cursor.execute('''
                    SELECT * FROM price_history 
                    WHERE product_id = ? AND recorded_at >= datetime('now', ?)
                    ORDER BY recorded_at DESC
                ''', (product_db_id, f'-{days} days'))
            else:
                cursor.execute('''
                    SELECT * FROM price_history 
                    WHERE product_id = ? 
                    ORDER BY recorded_at DESC
                ''', (product_db_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_price(self, product_db_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM price_history 
                WHERE product_id = ? 
                ORDER BY recorded_at DESC LIMIT 1
            ''', (product_db_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_price_stats(self, product_db_id: int) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    AVG(price) as avg_price,
                    COUNT(*) as record_count
                FROM price_history WHERE product_id = ?
            ''', (product_db_id,))
            row = cursor.fetchone()
            return dict(row)

    def delete_product(self, product_db_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM price_history WHERE product_id = ?', (product_db_id,))
            cursor.execute('DELETE FROM products WHERE id = ?', (product_db_id,))
            success = cursor.rowcount > 0
            if success:
                self.logger.info(f"删除商品成功: ID={product_db_id}")
            return success

    def update_target_price(self, product_db_id: int, target_price: float) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE products SET target_price = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (target_price, product_db_id))
            return cursor.rowcount > 0
