import click
import sys
from tabulate import tabulate
from price_monitor import ProductManager, PriceChangeDetector
from price_monitor.analyzer import PriceAnalyzer
from price_monitor.detector import ChangeType

if sys.platform == 'win32':
    import os
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')

@click.group()
def cli():
    """电商价格监控爬虫 - 功能A"""
    pass

@cli.command()
@click.argument('url')
@click.option('--target-price', '-t', type=float, help='目标价格')
def add(url, target_price):
    """添加商品监控"""
    manager = ProductManager()
    product = manager.add_product(url, target_price)
    if product:
        click.echo(f"✅ 添加成功: {product['name']}")
        click.echo(f"   ID: {product['id']}")
        click.echo(f"   当前价格: ¥{product.get('current_price', 0)}")
    else:
        click.echo("❌ 添加失败")

@cli.command()
@click.argument('product_id', type=int)
def remove(product_id):
    """删除商品监控"""
    manager = ProductManager()
    if manager.remove_product(product_id):
        click.echo(f"✅ 删除成功: 商品ID {product_id}")
    else:
        click.echo("❌ 删除失败")

@cli.command(name='list')
def list_products():
    """列出所有监控商品"""
    manager = ProductManager()
    products = manager.list_products()
    
    if not products:
        click.echo("暂无监控商品")
        return
    
    headers = ['ID', '商品名称', '平台', '当前价格', '最低价', '最高价', '目标价']
    rows = []
    for p in products:
        rows.append([
            p['id'],
            p['name'][:30] + '...' if len(p['name']) > 30 else p['name'],
            p['platform'],
            f"¥{p['current_price']:.2f}",
            f"¥{p['min_price']:.2f}",
            f"¥{p['max_price']:.2f}",
            f"¥{p['target_price']:.2f}" if p['target_price'] else '-'
        ])
    
    click.echo(tabulate(rows, headers=headers, tablefmt='simple'))
    click.echo(f"\n共 {len(products)} 个监控商品")

@cli.command()
@click.argument('product_id', type=int)
def detail(product_id):
    """查看商品详细信息和价格历史"""
    manager = ProductManager()
    data = manager.get_product_detail(product_id)
    
    if not data:
        click.echo("商品不存在")
        return
    
    product = data['product']
    stats = data['stats']
    history = data['price_history'][:10]
    
    click.echo(f"\n📦 {product['name']}")
    click.echo(f"   平台: {product['platform']}")
    click.echo(f"   URL: {product['url']}")
    click.echo(f"   目标价: ¥{product['target_price'] if product['target_price'] else '未设置'}")
    click.echo(f"\n📊 统计信息")
    click.echo(f"   最低价: ¥{stats['min_price']:.2f}")
    click.echo(f"   最高价: ¥{stats['max_price']:.2f}")
    click.echo(f"   平均价: ¥{stats['avg_price']:.2f}")
    click.echo(f"   记录数: {stats['record_count']}")
    
    click.echo(f"\n📈 最近价格记录")
    headers = ['时间', '价格']
    rows = [[h['recorded_at'], f"¥{h['price']:.2f}"] for h in history]
    click.echo(tabulate(rows, headers=headers, tablefmt='simple'))

@cli.command()
@click.argument('product_id', type=int, required=False)
def refresh(product_id):
    """刷新商品价格"""
    manager = ProductManager()
    
    if product_id:
        result = manager.refresh_product(product_id)
        if result:
            click.echo(f"✅ 刷新成功: {result['product']['name']}")
        else:
            click.echo("❌ 刷新失败")
    else:
        results = manager.refresh_all()
        click.echo(f"✅ 刷新完成: 成功更新 {len(results)} 个商品")

@cli.command()
@click.option('--discount', '-d', default=10.0, help='最低折扣率(%)')
def bargains(discount):
    """查看优惠商品（降价超过指定比例）"""
    detector = PriceChangeDetector()
    bargains = detector.get_bargains(discount)
    
    if not bargains:
        click.echo(f"暂无降价超过 {discount}% 的商品")
        return
    
    click.echo(f"🎁 降价超过 {discount}% 的商品:")
    for b in bargains:
        click.echo(f"\n  {b.product_name}")
        click.echo(f"    价格: ¥{b.old_price:.2f} → ¥{b.new_price:.2f}")
        click.echo(f"    降价: {b.change_percent:.1f}%")
        click.echo(f"    URL: {b.product_url}")

@cli.command()
def status():
    """查看监控状态摘要"""
    detector = PriceChangeDetector()
    summary = detector.get_summary()
    
    click.echo("\n📊 监控状态摘要")
    click.echo(f"   监控商品总数: {summary['total_products']}")
    click.echo(f"   价格变动商品: {summary['total_changes']}")
    click.echo(f"   降价: {summary['price_downs']} 个")
    click.echo(f"   涨价: {summary['price_ups']} 个")
    click.echo(f"   达到目标价: {summary['target_reached']} 个")

@cli.command()
def export_data():
    """导出数据（为功能B做准备）"""
    import json
    import sqlite3
    import os
    
    db_path = 'data/price_monitor.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM products')
    products = [dict(row) for row in cursor.fetchall()]
    
    for p in products:
        cursor.execute('SELECT * FROM price_history WHERE product_id = ? ORDER BY recorded_at', (p['id'],))
        p['price_history'] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    output_path = 'data/exported_data.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    
    click.echo(f"✅ 数据已导出到: {output_path}")
    click.echo(f"   包含 {len(products)} 个商品的完整价格历史")
    click.echo(f"   此数据可用于功能B - 自动生成分析报告")

@cli.command()
@click.option('--json', '-j', 'json_path', default='data/exported_data.json', help='JSON数据源路径')
@click.option('--format', '-f', 'formats', multiple=True, default=['markdown', 'excel'], 
              type=click.Choice(['markdown', 'excel', 'pdf']), 
              help='输出格式 (可多选: markdown, excel, pdf)')
def generate_report(json_path, formats):
    """生成价格监控分析报告 (功能B) - 综合7天+30天趋势"""
    click.echo("📊 正在生成价格监控智能分析报告...")
    click.echo("   分析维度: 7天短期 + 30天中期趋势对比")
    
    analyzer = PriceAnalyzer(json_path=json_path)
    results = analyzer.generate_full_report(formats=list(formats))
    
    click.echo("\n✅ 报告生成完成!")
    for fmt, path in results.items():
        if path:
            click.echo(f"   {fmt.upper()}: {path}")
    
    click.echo(f"\n📈 7天/30天价格走势图已保存到 reports/ 目录")

@cli.command()
@click.argument('product_id', type=int)
@click.option('--json', '-j', 'json_path', default='data/exported_data.json', help='JSON数据源路径')
def chart(product_id, json_path):
    """生成单个商品价格走势图 (7天+30天)"""
    analyzer = PriceAnalyzer(json_path=json_path)
    chart_path = analyzer.generate_dual_chart(product_id)
    
    if chart_path:
        click.echo(f"✅ 价格走势图已生成:")
        click.echo(f"   7天: reports/product_{product_id}_7days.png")
        click.echo(f"   30天: reports/product_{product_id}_30days.png")
    else:
        click.echo("❌ 生成失败: 商品不存在或价格记录不足")

if __name__ == '__main__':
    cli()
