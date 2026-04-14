import re
import time
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from ..config import Config
from ..logger import setup_logger

@dataclass
class ProductInfo:
    url: str
    platform: str
    product_id: str
    name: str
    price: float
    original_price: Optional[float] = None
    stock: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None

class BaseParser(ABC):
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)

    @abstractmethod
    def match(self, url: str) -> bool:
        pass

    @abstractmethod
    def extract_product_id(self, url: str) -> Optional[str]:
        pass

    @abstractmethod
    def parse(self, html: str, url: str) -> Optional[ProductInfo]:
        pass

class JDParser(BaseParser):
    def match(self, url: str) -> bool:
        return 'jd.com' in url

    def extract_product_id(self, url: str) -> Optional[str]:
        match = re.search(r'/(\d+)\.html', url)
        return match.group(1) if match else None

    def parse(self, html: str, url: str) -> Optional[ProductInfo]:
        try:
            soup = BeautifulSoup(html, 'lxml')
            product_id = self.extract_product_id(url)
            
            name_elem = soup.find('div', class_='sku-name') or soup.find('h1', class_='sku-name')
            name = name_elem.get_text(strip=True) if name_elem else '未知商品'
            
            price_elem = soup.find('span', class_='p-price')
            price = 0.0
            if price_elem:
                price_text = price_elem.get_text(strip=True).replace('¥', '').replace('￥', '')
                try:
                    price = float(price_text)
                except ValueError:
                    pass
            
            img_elem = soup.find('img', id='spec-img') or soup.find('img', class_='main-img')
            image_url = img_elem.get('src') if img_elem else None
            if image_url and image_url.startswith('//'):
                image_url = 'https:' + image_url

            return ProductInfo(
                url=url,
                platform='jd',
                product_id=product_id or '',
                name=name,
                price=price,
                image_url=image_url
            )
        except Exception as e:
            self.logger.error(f"解析京东商品失败: {e}")
            return None

class TaobaoParser(BaseParser):
    def match(self, url: str) -> bool:
        return 'taobao.com' in url or 'tmall.com' in url

    def extract_product_id(self, url: str) -> Optional[str]:
        match = re.search(r'id=(\d+)', url)
        return match.group(1) if match else None

    def parse(self, html: str, url: str) -> Optional[ProductInfo]:
        try:
            soup = BeautifulSoup(html, 'lxml')
            product_id = self.extract_product_id(url)
            
            name_elem = soup.find('h1', class_='main-title') or soup.find('h3', class_='tb-main-title')
            name = name_elem.get_text(strip=True) if name_elem else '未知商品'
            
            price_elem = soup.find('span', class_='tm-price') or soup.find('em', class_='tb-rmb-num')
            price = 0.0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                try:
                    price = float(price_text)
                except ValueError:
                    pass

            return ProductInfo(
                url=url,
                platform='taobao',
                product_id=product_id or '',
                name=name,
                price=price
            )
        except Exception as e:
            self.logger.error(f"解析淘宝商品失败: {e}")
            return None

class PriceSpider:
    def __init__(self):
        self.config = Config()
        self.logger = setup_logger(self.__class__.__name__)
        self.ua = UserAgent()
        self.parsers = [JDParser(), TaobaoParser()]
        self.session = requests.Session()
        
    def get_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def detect_platform(self, url: str) -> Optional[BaseParser]:
        for parser in self.parsers:
            if parser.match(url):
                return parser
        return None

    def random_delay(self):
        min_delay = self.config.get('spider.random_delay_min', 1)
        max_delay = self.config.get('spider.random_delay_max', 3)
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    def fetch_url(self, url: str) -> Optional[str]:
        timeout = self.config.get('spider.request_timeout', 30)
        retry_times = self.config.get('spider.retry_times', 3)
        retry_delay = self.config.get('spider.retry_delay', 5)

        for attempt in range(retry_times):
            try:
                response = self.session.get(
                    url,
                    headers=self.get_headers(),
                    timeout=timeout
                )
                response.encoding = 'utf-8'
                if response.status_code == 200:
                    return response.text
                self.logger.warning(f"请求失败，状态码: {response.status_code}, 尝试 {attempt + 1}/{retry_times}")
            except Exception as e:
                self.logger.warning(f"请求异常: {e}, 尝试 {attempt + 1}/{retry_times}")
            
            if attempt < retry_times - 1:
                time.sleep(retry_delay)
        
        self.logger.error(f"请求失败，已达最大重试次数: {url}")
        return None

    def crawl(self, url: str) -> Optional[ProductInfo]:
        self.logger.info(f"开始爬取: {url}")
        
        parser = self.detect_platform(url)
        if not parser:
            self.logger.error(f"不支持的平台: {url}")
            return None

        html = self.fetch_url(url)
        if not html:
            return None

        self.random_delay()
        
        product_info = parser.parse(html, url)
        if product_info:
            self.logger.info(f"爬取成功: {product_info.name} - 价格: ¥{product_info.price}")
        else:
            self.logger.warning(f"解析商品信息失败")
        
        return product_info
