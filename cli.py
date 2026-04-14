import click
import sys
from tabulate import tabulate
from price_monitor import ProductManager, PriceChangeDetector
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
@click.option('--format', '-f', type=click.Choice(['markdown', 'excel', 'pdf', 'all']), 
              default='all', help='报告格式 (markdown/excel/pdf/all)')
@click.option('--output', '-o', type=str, default='reports', help='输出目录')
@click.option('--use-json', is_flag=True, help='使用JSON数据源而非数据库')
@click.option('--source', '-s', type=click.Choice(['auto', 'database', 'json', 'merge']), 
              default='auto', help='数据源选择 (auto/database/json/merge)')
def report(format, output, use_json, source):
    """生成价格分析报告"""
    from price_monitor.report import ReportGenerator
    import os
    
    json_path = 'data/exported_data.json' if (use_json or source == 'json' or source == 'merge') else None
    
    generator = ReportGenerator(output_dir=output, json_path=json_path)
    
    click.echo("📊 正在分析数据...")
    generator.prepare_data(use_json=use_json, prefer_source=source)
    
    source_info = generator.summary.get('data_source_info')
    if source_info:
        click.echo(f"   数据源类型: {source_info.source_type}")
        click.echo(f"   商品数量: {source_info.product_count}")
        if source_info.has_conflict:
            click.echo(click.style(f"   ⚠️  检测到数据源冲突: {len(source_info.conflict_details)} 个问题", fg='yellow'))
            for conflict in source_info.conflict_details[:3]:
                click.echo(f"      - {conflict}")
            if len(source_info.conflict_details) > 3:
                click.echo(f"      - ... 还有 {len(source_info.conflict_details) - 3} 个问题")
            click.echo(click.style("   建议: 运行 'python cli.py export_data' 重新导出JSON数据", fg='cyan'))
    
    click.echo("📈 正在生成图表...")
    generator.generate_charts()
    
    reports = {}
    
    if format in ['markdown', 'all']:
        click.echo("📝 生成Markdown报告...")
        reports['markdown'] = generator.generate_markdown_report()
    
    if format in ['excel', 'all']:
        click.echo("📊 生成Excel报告...")
        reports['excel'] = generator.generate_excel_report()
    
    if format in ['pdf', 'all']:
        click.echo("📄 生成PDF报告...")
        reports['pdf'] = generator.generate_pdf_report()
    
    click.echo(f"\n✅ 报告生成完成!")
    click.echo(f"   报告目录: {os.path.abspath(output)}")
    for fmt, path in reports.items():
        click.echo(f"   {fmt.upper()}: {path}")

@cli.command()
@click.argument('product_id', type=int)
@click.option('--days', '-d', default=30, help='显示天数')
@click.option('--output', '-o', type=str, default='reports/charts', help='输出目录')
def chart(product_id, days, output):
    """生成单个商品的价格趋势图"""
    from price_monitor.report import PriceAnalyzer, PriceVisualizer
    from price_monitor.storage import Database
    
    db = Database()
    product = db.get_product(product_id)
    
    if not product:
        click.echo(f"❌ 商品ID {product_id} 不存在")
        return
    
    history = db.get_price_history(product_id)
    if not history:
        click.echo(f"❌ 商品 {product['name']} 暂无价格历史")
        return
    
    analyzer = PriceAnalyzer()
    analysis = analyzer.analyze_product(product, history)
    
    visualizer = PriceVisualizer(output_dir=output)
    chart_path = visualizer.plot_price_trend(analysis, days=days)
    
    click.echo(f"✅ 价格趋势图已生成: {chart_path}")

@cli.command()
@click.option('--top', '-n', default=5, help='显示TOP N商品')
@click.option('--output', '-o', type=str, default='reports/charts', help='输出目录')
def compare(top, output):
    """生成多商品价格对比图"""
    from price_monitor.report import PriceAnalyzer, PriceVisualizer
    
    analyzer = PriceAnalyzer()
    analyses = analyzer.analyze_all()
    
    if not analyses:
        click.echo("暂无商品数据")
        return
    
    top_products = sorted(analyses, 
                         key=lambda x: abs(x.change_percent_recent), 
                         reverse=True)[:top]
    
    visualizer = PriceVisualizer(output_dir=output)
    chart_path = visualizer.plot_multi_product_comparison(top_products)
    
    click.echo(f"✅ 商品对比图已生成: {chart_path}")
    click.echo(f"   包含商品:")
    for a in top_products:
        click.echo(f"   - {a.product_name[:30]}")

if __name__ == '__main__':
    cli()
