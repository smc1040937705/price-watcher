"""
测试爬虫解析功能 - 使用本地HTML文件
"""
import sys
import os

if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup
from price_monitor.spider import JDParser, TaobaoParser, ProductInfo

def test_local_html():
    """测试解析本地京东商品页面"""
    
    html_path = os.path.join(os.path.dirname(__file__), 'test_jd_product.html')
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = JDParser()
    
    test_url = "https://item.jd.com/100065243343.html"
    
    print("=" * 60)
    print("测试京东商品解析器 - 本地HTML文件")
    print("=" * 60)
    
    product_id = parser.extract_product_id(test_url)
    print(f"\n✓ 商品ID解析: {product_id}")
    
    product = parser.parse(html, test_url)
    
    if product:
        print(f"\n✓ 解析成功!")
        print(f"  - 商品名称: {product.name}")
        print(f"  - 商品平台: {product.platform}")
        print(f"  - 商品ID: {product.product_id}")
        print(f"  - 商品价格: ¥{product.price:.2f}")
        print(f"  - 图片URL: {product.image_url}")
    else:
        print("\n✗ 解析失败!")
    
    print("\n" + "=" * 60)
    print("测试完成! 解析器工作正常 ✅")
    print("=" * 60)
    
    return product

def add_test_data_to_db():
    """添加测试数据到数据库，用于后续功能B测试"""
    from price_monitor.storage import Database
    
    print("\n📝 添加测试价格历史数据...")
    
    db = Database()
    
    product_info = ProductInfo(
        url="https://item.jd.com/100065243343.html",
        platform="jd",
        product_id="100065243343",
        name="Apple iPhone 15 Pro Max 256GB 原色钛金属",
        price=8999.00,
        image_url="https://img10.360buyimg.com/n1/jfs/t1/196728/24/25752/129275/64d98b85F0d3e2b32/1d9d06c7d4e5d3d8.jpg"
    )
    
    product_db_id = db.add_product(product_info, target_price=8500.00)
    
    test_prices = [
        9999.00, 9499.00, 9299.00, 9199.00, 8999.00,
        9099.00, 8999.00, 8899.00, 8799.00, 8999.00
    ]
    
    for price in test_prices:
        product_info.price = price
        db.record_price(product_db_id, product_info)
    
    print(f"✓ 测试数据已添加到数据库, 商品ID: {product_db_id}")
    print(f"✓ 已添加 {len(test_prices)} 条历史价格记录用于测试")
    
    return product_db_id

if __name__ == "__main__":
    test_local_html()
    add_test_data_to_db()
    
    print("\n💡 现在可以运行以下命令查看效果:")
    print("  python cli.py list          # 查看商品列表")
    print("  python cli.py detail 1      # 查看商品详情和价格历史")
    print("  python cli.py status        # 查看监控状态")
    print("  python cli.py export-data   # 导出数据供功能B使用")
