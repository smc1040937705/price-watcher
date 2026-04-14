import click
import sys
from tabulate import tabulate
from price_monitor import ProductManager, PriceChangeDetector, TrendAnalyzer, ReportGenerator
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
@click.option('--days', '-d', default='7,30', help='分析天数，多个用逗号分隔(默认"7,30")')
@click.option('--output-dir', '-o', default='reports', help='报告输出目录')
@click.option('--json-source', '-j', default=None, help='JSON数据源路径(默认data/exported_data.json)')
@click.option('--combined/--no-combined', default=True, help='使用联合数据源模式(同时读取SQLite和JSON)')
def report(days, output_dir, json_source, combined):
    """生成价格分析报告(Markdown/Excel/PDF/图表)，支持多时间段对比和双数据源"""
    # 解析天数列表
    try:
        days_list = [int(d.strip()) for d in days.split(',')]
    except ValueError:
        days_list = [7, 30]
    
    click.echo(f"📊 正在生成价格分析报告({', '.join([f'{d}天' for d in days_list])})...")
    
    if combined:
        click.echo("🔗 使用联合数据源模式(SQLite + JSON)")
        json_path = json_source or "data/exported_data.json"
    elif json_source:
        click.echo(f"📁 仅使用JSON数据源: {json_source}")
        json_path = json_source
    else:
        click.echo("📁 仅使用SQLite数据源")
        json_path = None
    
    generator = ReportGenerator(output_dir=output_dir, json_path=json_path, use_combined=combined)
    reports = generator.generate_all_reports(days_list=days_list)
    
    click.echo("\n✅ 报告生成完成!")
    click.echo(f"\n📄 Markdown报告: {reports.get('markdown', 'N/A')}")
    click.echo(f"📊 Excel报告: {reports.get('excel', 'N/A')}")
    click.echo(f"📑 PDF报告: {reports.get('pdf', 'N/A')}")
    click.echo(f"📈 趋势图表: {reports.get('charts', 'N/A')}")
    click.echo(f"📊 对比图表: {reports.get('compare_charts', 'N/A')}")
    
    # 显示汇总统计（多时间段）
    if combined:
        from price_monitor.analyzer import CombinedTrendAnalyzer
        analyzer = CombinedTrendAnalyzer(json_path=json_path)
        click.echo(f"\n📈 监控概览对比 (联合数据源):")
    else:
        from price_monitor import TrendAnalyzer
        analyzer = TrendAnalyzer()
        click.echo(f"\n📈 监控概览对比:")
    
    for d in days_list:
        summary = analyzer.get_summary_stats(d)
        click.echo(f"\n   【{d}天周期】")
        click.echo(f"      监控商品总数: {summary['total_products']}")
        click.echo(f"      降价商品数: {summary['price_down_count']}")
        click.echo(f"      涨价商品数: {summary['price_up_count']}")
        click.echo(f"      达到目标价: {summary['target_reached_count']}")
        
        # 显示数据源统计
        if combined and 'data_sources' in summary:
            ds = summary['data_sources']
            click.echo(f"      数据源分布: SQLite仅{ds.get('sqlite_only',0)}, JSON仅{ds.get('json_only',0)}, 双源{ds.get('both',0)}")
            if ds.get('conflicts', 0) > 0:
                click.echo(f"      ⚠️ 数据冲突: {ds['conflicts']}个商品")

@cli.command()
@click.argument('product_id', type=int)
@click.option('--days', '-d', default=7, help='分析天数(默认7天)')
def analyze(product_id, days):
    """分析单个商品的价格趋势"""
    analyzer = TrendAnalyzer()
    result = analyzer.analyze_product(product_id, days)
    
    if not result:
        click.echo("❌ 商品不存在或无价格历史")
        return
    
    click.echo(f"\n📦 {result.product_name}")
    click.echo(f"   平台: {result.platform}")
    click.echo(f"\n💰 价格统计:")
    click.echo(f"   当前价格: ¥{result.current_price:.2f}")
    click.echo(f"   最低价: ¥{result.min_price:.2f}")
    click.echo(f"   最高价: ¥{result.max_price:.2f}")
    click.echo(f"   平均价: ¥{result.avg_price:.2f}")
    
    click.echo(f"\n📊 趋势分析(最近{days}天):")
    click.echo(f"   涨跌额: ¥{result.price_change:.2f}")
    click.echo(f"   涨跌幅: {result.change_percent:+.2f}%")
    click.echo(f"   波动范围: ¥{result.volatility_range:.2f} ({result.volatility_percent:.2f}%)")
    
    trend_icon = "📈" if result.trend_direction == "up" else "📉" if result.trend_direction == "down" else "➡️"
    trend_text = "上涨" if result.trend_direction == "up" else "下跌" if result.trend_direction == "down" else "稳定"
    click.echo(f"   趋势方向: {trend_icon} {trend_text}")
    
    if result.target_price:
        click.echo(f"\n🎯 目标价格:")
        click.echo(f"   目标价: ¥{result.target_price:.2f}")
        if result.current_price <= result.target_price:
            click.echo(f"   状态: ✅ 已达标 (低¥{abs(result.target_diff):.2f})")
        else:
            click.echo(f"   状态: ⏳ 未达标 (还需降{result.target_diff_percent:.1f}%)")

if __name__ == '__main__':
    cli()
