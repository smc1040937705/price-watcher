#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
价格分析报告生成示例脚本
演示如何使用价格分析模块生成各种格式的报告
支持多时间段对比(7天/30天)和双数据源联合分析
"""

import os
import sys
from price_monitor import TrendAnalyzer, ReportGenerator
from price_monitor.analyzer import CombinedTrendAnalyzer


def main():
    # 1. 使用联合数据源趋势分析器分析商品
    print("=" * 70)
    print("Price Trend Analysis Demo - Combined Data Sources")
    print("=" * 70)
    
    # 使用联合数据源分析器(同时读取SQLite和JSON)
    json_path = "data/exported_data.json"
    use_combined = os.path.exists(json_path)
    
    if use_combined:
        print("\n[联合数据源模式] 同时读取SQLite和JSON数据源")
        analyzer = CombinedTrendAnalyzer(json_path=json_path)
    else:
        print("\n[单数据源模式] 仅使用SQLite数据库")
        analyzer = TrendAnalyzer()
    
    # 获取多时间段汇总统计
    days_list = [7, 30]
    print("\nMonitoring Overview (Multi-Period Comparison):")
    for days in days_list:
        summary = analyzer.get_summary_stats(days=days)
        print(f"\n  [{days} Days]:")
        print(f"    Total Products: {summary['total_products']}")
        print(f"    Price Down: {summary['price_down_count']}")
        print(f"    Price Up: {summary['price_up_count']}")
        print(f"    Target Reached: {summary['target_reached_count']}")
        
        # 显示数据源统计
        if 'data_sources' in summary:
            ds = summary['data_sources']
            print(f"    Data Sources:")
            print(f"      - SQLite Only: {ds.get('sqlite_only', 0)}")
            print(f"      - JSON Only: {ds.get('json_only', 0)}")
            print(f"      - Both Sources: {ds.get('both', 0)}")
            if ds.get('conflicts', 0) > 0:
                print(f"      ⚠️ Conflicts: {ds['conflicts']} products")
    
    # 获取降价商品
    down_products = analyzer.get_price_down_products(days=7)
    print(f"\nPrice Down Products (7 days) ({len(down_products)}):")
    for p in down_products[:5]:
        print(f"  - {p.product_name[:40]}: {p.current_price:.2f} (down {p.change_percent:.1f}%)")
    
    # 获取涨价商品
    up_products = analyzer.get_price_up_products(days=7)
    print(f"\nPrice Up Products (7 days) ({len(up_products)}):")
    for p in up_products[:5]:
        print(f"  - {p.product_name[:40]}: {p.current_price:.2f} (up {p.change_percent:.1f}%)")
    
    # 显示数据冲突
    if use_combined and hasattr(analyzer, 'get_all_conflicts'):
        conflicts = analyzer.get_all_conflicts()
        if conflicts:
            print(f"\n⚠️ Data Conflicts ({len(conflicts)} products):")
            for c in conflicts:
                print(f"  - {c['product_name']} (ID: {c['product_id']})")
                for conflict in c['conflicts']:
                    if conflict['type'] == 'price_mismatch':
                        print(f"    Price: SQLite ¥{conflict['sqlite_price']:.2f} vs JSON ¥{conflict['json_price']:.2f}")
    
    # 2. 生成完整报告（多时间段对比 + 双数据源）
    print("\n" + "=" * 70)
    print("Generating Multi-Period Reports with Combined Data Sources")
    print("=" * 70)
    
    if use_combined:
        print(f"\nUsing Combined Data Sources (SQLite + JSON)")
        generator = ReportGenerator(output_dir="reports", json_path=json_path, use_combined=True)
    else:
        print("\nUsing SQLite database only")
        generator = ReportGenerator(output_dir="reports", use_combined=False)
    
    # 生成7天和30天对比报告
    reports = generator.generate_all_reports(days_list=[7, 30])
    
    print("\nReports Generated:")
    print(f"  Markdown: {reports.get('markdown', 'N/A')}")
    print(f"  Excel: {reports.get('excel', 'N/A')}")
    print(f"  PDF: {reports.get('pdf', 'N/A')}")
    print(f"  Charts: {reports.get('charts', 'N/A')}")
    print(f"  Compare Charts: {reports.get('compare_charts', 'N/A')}")
    
    # 3. 生成汇总图表
    print("\nGenerating Summary Charts...")
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for days in [7, 30]:
        summary_chart_path = f"reports/summary_chart_{days}d_{timestamp}.png"
        chart_path = generator.generate_summary_chart(summary_chart_path, days=days)
        if chart_path:
            print(f"  Summary Chart ({days}d): {chart_path}")
    
    print("\n" + "=" * 70)
    print("Analysis Complete!")
    print("=" * 70)
    print("\nYou can also use the CLI command:")
    print("  python cli.py report                    # 联合数据源模式(默认)")
    print("  python cli.py report --no-combined      # 仅SQLite数据源")
    print("  python cli.py report --json-source path # 指定JSON路径")


if __name__ == "__main__":
    main()
