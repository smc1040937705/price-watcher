"""
报告生成器 - 生成Markdown/Excel/PDF格式的分析报告
"""

import os
import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .trend_analyzer import TrendAnalyzer, TrendResult
from ..storage import Database
from ..logger import setup_logger


class ReportGenerator:
    """价格分析报告生成器"""
    
    def __init__(self, output_dir: str = "reports", db: Database = None, json_path: str = None, 
                 use_combined: bool = True):
        """
        初始化报告生成器
        
        Args:
            output_dir: 报告输出目录
            db: 数据库实例
            json_path: JSON文件路径
            use_combined: 是否使用联合数据源分析器(同时读取SQLite和JSON)
        """
        self.logger = setup_logger(self.__class__.__name__)
        self.db = db
        self.json_path = json_path
        self.use_combined = use_combined
        self.analyzer = self._create_analyzer()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_analyzer(self):
        """创建趋势分析器"""
        if self.use_combined:
            # 使用联合数据源分析器(同时读取SQLite和JSON)
            return CombinedTrendAnalyzer(self.db, self.json_path)
        elif self.json_path and os.path.exists(self.json_path):
            # 仅使用JSON数据源
            return JsonTrendAnalyzer(self.json_path)
        else:
            # 仅使用SQLite数据源
            return TrendAnalyzer(self.db)
    
    def generate_all_reports(self, days_list: List[int] = None) -> Dict[str, str]:
        """生成所有格式的报告，支持多时间段对比"""
        if days_list is None:
            days_list = [7, 30]  # 默认生成7天和30天对比
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        reports = {}
        
        # 生成Markdown报告（包含多时间段对比）
        md_path = self.output_dir / f"price_report_{timestamp}.md"
        reports['markdown'] = self.generate_markdown_report(str(md_path), days_list)
        
        # 生成Excel报告
        excel_path = self.output_dir / f"price_report_{timestamp}.xlsx"
        reports['excel'] = self.generate_excel_report(str(excel_path), days_list)
        
        # 生成PDF报告
        pdf_path = self.output_dir / f"price_report_{timestamp}.pdf"
        reports['pdf'] = self.generate_pdf_report(str(pdf_path), days_list)
        
        # 生成图表
        chart_path = self.output_dir / f"price_charts_{timestamp}.png"
        reports['charts'] = self.generate_charts(str(chart_path), days_list[0])
        
        # 生成对比图表
        compare_chart_path = self.output_dir / f"price_compare_{timestamp}.png"
        reports['compare_charts'] = self.generate_comparison_charts(str(compare_chart_path), days_list)
        
        self.logger.info(f"报告生成完成: {reports}")
        return reports
    
    def generate_markdown_report(self, output_path: str, days_list: List[int] = None) -> str:
        """生成Markdown格式的分析报告，支持多时间段对比"""
        if days_list is None:
            days_list = [7, 30]
        
        report_date = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        lines = []
        
        # 报告标题
        lines.append("# 电商价格监控分析报告")
        lines.append("")
        lines.append(f"**生成时间**: {report_date}")
        lines.append(f"**分析周期**: {', '.join([f'{d}天' for d in days_list])}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 多时间段监控概览对比
        lines.append("## 监控概览对比")
        lines.append("")
        
        # 构建对比表格
        headers = ["指标"] + [f"{d}天" for d in days_list]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["------"] * len(headers)) + "|")
        
        summaries = {days: self.analyzer.get_summary_stats(days) for days in days_list}
        
        metrics = [
            ("监控商品总数", "total_products", "{:.0f}"),
            ("降价商品数", "price_down_count", "{:.0f}"),
            ("涨价商品数", "price_up_count", "{:.0f}"),
            ("价格稳定商品数", "stable_count", "{:.0f}"),
            ("达到目标价商品数", "target_reached_count", "{:.0f}"),
            ("平均涨跌幅", "avg_change_percent", "{:.2f}%"),
        ]
        
        for label, key, fmt in metrics:
            row_values = [label]
            for days in days_list:
                val = summaries[days].get(key, 0)
                row_values.append(fmt.format(val))
            lines.append("| " + " | ".join(row_values) + " |")
        
        lines.append("")
        
        # 添加数据源统计信息（如果是联合数据源模式）
        if self.use_combined and hasattr(self.analyzer, 'get_summary_stats'):
            primary_summary = summaries.get(min(days_list), {})
            data_sources = primary_summary.get('data_sources', {})
            if data_sources:
                lines.append("## 数据源统计")
                lines.append("")
                lines.append("| 数据来源 | 商品数量 | 说明 |")
                lines.append("|----------|----------|------|")
                lines.append(f"| 仅SQLite | {data_sources.get('sqlite_only', 0)} | 仅在数据库中存在的商品 |")
                lines.append(f"| 仅JSON | {data_sources.get('json_only', 0)} | 仅在JSON文件中存在的商品 |")
                lines.append(f"| 双数据源 | {data_sources.get('both', 0)} | 两个数据源都存在的商品 |")
                lines.append(f"| **总计** | **{data_sources.get('sqlite_only', 0) + data_sources.get('json_only', 0) + data_sources.get('both', 0)}** | |")
                lines.append("")
                
                # 显示冲突信息
                conflict_count = data_sources.get('conflicts', 0)
                if conflict_count > 0:
                    lines.append(f"> ⚠️ **注意**: 发现 {conflict_count} 个商品存在数据冲突，详见下方[数据冲突报告](#数据冲突报告)")
                    lines.append("")
        
        lines.append("---")
        lines.append("")
        
        # 获取主要分析周期（最短周期）的数据
        primary_days = min(days_list)
        down_products = self.analyzer.get_price_down_products(primary_days)
        up_products = self.analyzer.get_price_up_products(primary_days)
        target_reached = self.analyzer.get_target_reached_products(primary_days)
        all_products = self.analyzer.analyze_all_products(primary_days)
        
        # 降价商品清单
        lines.append("## 降价商品清单")
        lines.append("")
        if down_products:
            lines.append("| 商品名称 | 平台 | 当前价格 | 涨跌额 | 涨跌幅 | 趋势 |")
            lines.append("|----------|------|----------|--------|--------|------|")
            for p in down_products[:20]:
                name = p.product_name[:30] + "..." if len(p.product_name) > 30 else p.product_name
                trend_icon = "下跌"
                lines.append(f"| {name} | {p.platform} | {p.current_price:.2f} | {p.price_change:.2f} | {p.change_percent:.2f}% | {trend_icon} |")
        else:
            lines.append("*暂无降价商品*")
        lines.append("")
        
        # 涨价商品清单
        lines.append("## 涨价商品清单")
        lines.append("")
        if up_products:
            lines.append("| 商品名称 | 平台 | 当前价格 | 涨跌额 | 涨跌幅 | 趋势 |")
            lines.append("|----------|------|----------|--------|--------|------|")
            for p in up_products[:20]:
                name = p.product_name[:30] + "..." if len(p.product_name) > 30 else p.product_name
                trend_icon = "上涨"
                lines.append(f"| {name} | {p.platform} | {p.current_price:.2f} | +{p.price_change:.2f} | +{p.change_percent:.2f}% | {trend_icon} |")
        else:
            lines.append("*暂无涨价商品*")
        lines.append("")
        
        # 达到目标价商品
        lines.append("## 达到目标价商品")
        lines.append("")
        if target_reached:
            lines.append("| 商品名称 | 平台 | 当前价格 | 目标价格 | 差额 | 节省 |")
            lines.append("|----------|------|----------|----------|------|------|")
            for p in target_reached:
                name = p.product_name[:30] + "..." if len(p.product_name) > 30 else p.product_name
                diff = p.target_price - p.current_price
                lines.append(f"| {name} | {p.platform} | {p.current_price:.2f} | {p.target_price:.2f} | -{diff:.2f} | {diff:.2f} |")
        else:
            lines.append("*暂无达到目标价的商品*")
        lines.append("")
        
        # 重点商品趋势分析（完善版）
        lines.append("## 重点商品趋势分析")
        lines.append("")
        lines.append("> 本部分展示价格波动最大、最值得关注的商品详细分析")
        lines.append("")
        
        # 选择波动最大的商品作为重点分析
        volatile_products = sorted(all_products, key=lambda x: abs(x.change_percent), reverse=True)[:5]
        
        for i, p in enumerate(volatile_products, 1):
            lines.append(f"### {i}. {p.product_name}")
            lines.append("")
            
            # 商品基本信息
            lines.append("#### 基本信息")
            lines.append(f"- **平台**: {p.platform}")
            lines.append(f"- **商品ID**: {p.product_id}")
            lines.append(f"- **当前价格**: {p.current_price:.2f}")
            lines.append("")
            
            # 多时间段价格统计对比
            lines.append("#### 价格统计对比")
            lines.append("")
            lines.append("| 统计项 | " + " | ".join([f"{d}天" for d in days_list]) + " |")
            lines.append("|--------|" + "|".join(["--------"] * len(days_list)) + "|")
            
            # 为每个时间段获取数据
            min_prices = []
            max_prices = []
            avg_prices = []
            change_percents = []
            
            for days in days_list:
                result = self.analyzer.analyze_product(p.product_id, days)
                if result:
                    min_prices.append(f"{result.min_price:.2f}")
                    max_prices.append(f"{result.max_price:.2f}")
                    avg_prices.append(f"{result.avg_price:.2f}")
                    change_percents.append(f"{result.change_percent:+.2f}%")
                else:
                    min_prices.append("N/A")
                    max_prices.append("N/A")
                    avg_prices.append("N/A")
                    change_percents.append("N/A")
            
            lines.append("| 最低价 | " + " | ".join(min_prices) + " |")
            lines.append("| 最高价 | " + " | ".join(max_prices) + " |")
            lines.append("| 平均价 | " + " | ".join(avg_prices) + " |")
            lines.append("| 涨跌幅 | " + " | ".join(change_percents) + " |")
            lines.append("")
            
            # 当前周期详细分析
            lines.append(f"#### {primary_days}天详细分析")
            lines.append("")
            lines.append(f"- **最低价**: {p.min_price:.2f}")
            lines.append(f"- **最高价**: {p.max_price:.2f}")
            lines.append(f"- **平均价**: {p.avg_price:.2f}")
            lines.append(f"- **涨跌额**: {p.price_change:.2f}")
            lines.append(f"- **涨跌幅**: {p.change_percent:+.2f}%")
            lines.append(f"- **波动范围**: {p.volatility_range:.2f} ({p.volatility_percent:.2f}%)")
            
            trend_text = "上涨" if p.trend_direction == "up" else "下跌" if p.trend_direction == "down" else "稳定"
            lines.append(f"- **趋势方向**: {trend_text}")
            
            if p.target_price:
                lines.append(f"- **目标价格**: {p.target_price:.2f}")
                if p.current_price <= p.target_price:
                    lines.append(f"- **距离目标**: 已达标 (低{abs(p.target_diff):.2f})")
                else:
                    lines.append(f"- **距离目标**: 未达标 (还需降{p.target_diff_percent:.1f}%)")
            lines.append("")
            
            # 价格历史表格
            if p.price_history:
                lines.append("#### 价格历史")
                lines.append("")
                lines.append("| 时间 | 价格 | 变动 |")
                lines.append("|------|------|------|")
                
                prev_price = None
                for h in p.price_history[-15:]:  # 显示最近15条
                    recorded_at = h.get('recorded_at', 'N/A')
                    price = h.get('price', 0)
                    
                    if prev_price is not None:
                        change = price - prev_price
                        if change > 0:
                            change_str = f"+{change:.2f} 上涨"
                        elif change < 0:
                            change_str = f"-{abs(change):.2f} 下跌"
                        else:
                            change_str = "- 稳定"
                    else:
                        change_str = "-"
                    
                    lines.append(f"| {recorded_at} | {price:.2f} | {change_str} |")
                    prev_price = price
                
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        # 添加数据冲突报告（如果是联合数据源模式且有冲突）
        if self.use_combined and hasattr(self.analyzer, 'get_all_conflicts'):
            conflicts = self.analyzer.get_all_conflicts()
            if conflicts:
                lines.append("## 数据冲突报告")
                lines.append("")
                lines.append("> 以下商品在SQLite数据库和JSON文件中的数据存在差异")
                lines.append("")
                
                for i, conflict_info in enumerate(conflicts, 1):
                    lines.append(f"### {i}. {conflict_info['product_name']} (ID: {conflict_info['product_id']})")
                    lines.append("")
                    lines.append(f"**数据来源**: {', '.join(conflict_info['sources'])}")
                    lines.append("")
                    
                    for conflict in conflict_info['conflicts']:
                        if conflict['type'] == 'price_mismatch':
                            lines.append(f"- ⚠️ **价格不一致**:")
                            lines.append(f"  - SQLite: ¥{conflict['sqlite_price']:.2f}")
                            lines.append(f"  - JSON: ¥{conflict['json_price']:.2f}")
                            lines.append(f"  - 差异: ¥{conflict['diff']:.2f} ({conflict['diff_percent']:.2f}%)")
                        elif conflict['type'] == 'name_mismatch':
                            lines.append(f"- ⚠️ **名称不一致**:")
                            lines.append(f"  - SQLite: {conflict['sqlite_name']}")
                            lines.append(f"  - JSON: {conflict['json_name']}")
                    
                    lines.append("")
                
                lines.append("---")
                lines.append("")
        
        lines.append("*报告由电商价格监控系统自动生成*")
        
        # 写入文件
        content = "\n".join(lines)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.logger.info(f"Markdown报告已生成: {output_path}")
        return output_path
    
    def generate_excel_report(self, output_path: str, days_list: List[int] = None) -> str:
        """生成Excel格式的分析报告，支持多时间段"""
        if days_list is None:
            days_list = [7, 30]
        
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            self.logger.error("缺少openpyxl库，无法生成Excel报告")
            return self._generate_json_report(output_path.replace('.xlsx', '.json'), days_list)
        
        wb = openpyxl.Workbook()
        
        # 样式定义
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        alignment_center = Alignment(horizontal='center')
        
        # 1. 概览工作表（多时间段对比）
        ws_overview = wb.active
        ws_overview.title = "监控概览"
        
        ws_overview.append(["电商价格监控概览对比"])
        ws_overview.merge_cells('A1:D1')
        ws_overview['A1'].font = Font(bold=True, size=14)
        ws_overview['A1'].alignment = alignment_center
        
        ws_overview.append(["生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "", ""])
        ws_overview.append([])
        
        # 多时间段对比表
        headers = ["指标"] + [f"{d}天" for d in days_list]
        ws_overview.append(headers)
        
        for cell in ws_overview[4]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = alignment_center
        
        summaries = {days: self.analyzer.get_summary_stats(days) for days in days_list}
        
        metrics = [
            ("监控商品总数", "total_products"),
            ("降价商品数", "price_down_count"),
            ("涨价商品数", "price_up_count"),
            ("价格稳定商品数", "stable_count"),
            ("达到目标价商品数", "target_reached_count"),
            ("平均涨跌幅(%)", "avg_change_percent"),
        ]
        
        for label, key in metrics:
            row = [label]
            for days in days_list:
                row.append(summaries[days].get(key, 0))
            ws_overview.append(row)
        
        # 设置列宽
        ws_overview.column_dimensions['A'].width = 20
        for col in range(2, len(headers) + 1):
            ws_overview.column_dimensions[get_column_letter(col)].width = 15
        
        # 2. 降价商品工作表
        primary_days = min(days_list)
        ws_down = wb.create_sheet("降价商品")
        down_products = self.analyzer.get_price_down_products(primary_days)
        self._fill_product_sheet(ws_down, down_products, "降价商品清单", 
                                header_font, header_fill, border, alignment_center, get_column_letter)
        
        # 3. 涨价商品工作表
        ws_up = wb.create_sheet("涨价商品")
        up_products = self.analyzer.get_price_up_products(primary_days)
        self._fill_product_sheet(ws_up, up_products, "涨价商品清单", 
                                header_font, header_fill, border, alignment_center, get_column_letter)
        
        # 4. 达到目标价工作表
        ws_target = wb.create_sheet("达到目标价")
        target_products = self.analyzer.get_target_reached_products(primary_days)
        self._fill_target_sheet(ws_target, target_products, 
                               header_font, header_fill, border, alignment_center, get_column_letter)
        
        # 5. 所有商品详情（包含多时间段数据）
        ws_all = wb.create_sheet("所有商品详情")
        all_products = self.analyzer.analyze_all_products(primary_days)
        self._fill_all_products_sheet(ws_all, all_products, days_list,
                                     header_font, header_fill, border, alignment_center, get_column_letter)
        
        # 6. 重点商品分析
        ws_key = wb.create_sheet("重点商品分析")
        volatile_products = sorted(all_products, key=lambda x: abs(x.change_percent), reverse=True)[:10]
        self._fill_key_products_sheet(ws_key, volatile_products, days_list,
                                     header_font, header_fill, border, alignment_center, get_column_letter)
        
        wb.save(output_path)
        self.logger.info(f"Excel报告已生成: {output_path}")
        return output_path
    
    def generate_pdf_report(self, output_path: str, days_list: List[int] = None) -> str:
        """生成PDF格式的分析报告"""
        if days_list is None:
            days_list = [7, 30]
        
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
        except ImportError:
            self.logger.error("缺少reportlab库，无法生成PDF报告")
            # 尝试使用weasyprint作为备选
            try:
                return self._generate_pdf_with_weasyprint(output_path, days_list)
            except ImportError:
                self.logger.error("缺少PDF生成库，将生成HTML报告作为替代")
                return self._generate_html_report(output_path.replace('.pdf', '.html'), days_list)
        
        # 注册中文字体
        try:
            pdfmetrics.registerFont(TTFont('SimHei', 'simhei.ttf'))
            chinese_font = 'SimHei'
        except:
            try:
                pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
                chinese_font = 'DejaVuSans'
            except:
                chinese_font = 'Helvetica'
        
        doc = SimpleDocTemplate(output_path, pagesize=A4,
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=chinese_font,
            fontSize=20,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=chinese_font,
            fontSize=14,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=12
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=chinese_font,
            fontSize=10,
            leading=14
        )
        
        story = []
        
        # 标题
        story.append(Paragraph("电商价格监控分析报告", title_style))
        story.append(Spacer(1, 0.5*cm))
        
        # 报告信息
        report_date = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        story.append(Paragraph(f"生成时间: {report_date}", normal_style))
        story.append(Paragraph(f"分析周期: {', '.join([f'{d}天' for d in days_list])}", normal_style))
        story.append(Spacer(1, 1*cm))
        
        # 监控概览
        story.append(Paragraph("监控概览对比", heading_style))
        story.append(Spacer(1, 0.3*cm))
        
        summaries = {days: self.analyzer.get_summary_stats(days) for days in days_list}
        
        # 概览表格
        overview_data = [["指标"] + [f"{d}天" for d in days_list]]
        metrics = [
            ("监控商品总数", "total_products", "{:.0f}"),
            ("降价商品数", "price_down_count", "{:.0f}"),
            ("涨价商品数", "price_up_count", "{:.0f}"),
            ("达到目标价", "target_reached_count", "{:.0f}"),
            ("平均涨跌幅", "avg_change_percent", "{:.2f}%"),
        ]
        
        for label, key, fmt in metrics:
            row = [label]
            for days in days_list:
                val = summaries[days].get(key, 0)
                row.append(fmt.format(val))
            overview_data.append(row)
        
        overview_table = Table(overview_data, colWidths=[4*cm] + [3*cm]*len(days_list))
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), chinese_font),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), chinese_font),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        story.append(overview_table)
        story.append(Spacer(1, 1*cm))
        
        # 降价商品
        primary_days = min(days_list)
        down_products = self.analyzer.get_price_down_products(primary_days)[:10]
        
        if down_products:
            story.append(PageBreak())
            story.append(Paragraph("降价商品清单", heading_style))
            story.append(Spacer(1, 0.3*cm))
            
            down_data = [["商品名称", "平台", "当前价格", "涨跌幅"]]
            for p in down_products:
                name = p.product_name[:25] + "..." if len(p.product_name) > 25 else p.product_name
                down_data.append([name, p.platform, f"{p.current_price:.2f}", f"{p.change_percent:.2f}%"])
            
            down_table = Table(down_data, colWidths=[7*cm, 2*cm, 3*cm, 3*cm])
            down_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), chinese_font),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightpink),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (-1, -1), chinese_font),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(down_table)
            story.append(Spacer(1, 1*cm))
        
        # 重点商品分析
        all_products = self.analyzer.analyze_all_products(primary_days)
        volatile_products = sorted(all_products, key=lambda x: abs(x.change_percent), reverse=True)[:5]
        
        if volatile_products:
            story.append(PageBreak())
            story.append(Paragraph("重点商品趋势分析", heading_style))
            story.append(Spacer(1, 0.3*cm))
            
            for i, p in enumerate(volatile_products, 1):
                story.append(Paragraph(f"{i}. {p.product_name[:40]}", 
                                      ParagraphStyle('ProductTitle', parent=heading_style, fontSize=12)))
                
                product_data = [
                    ["指标", "数值"],
                    ["当前价格", f"{p.current_price:.2f}"],
                    ["最低价", f"{p.min_price:.2f}"],
                    ["最高价", f"{p.max_price:.2f}"],
                    ["涨跌幅", f"{p.change_percent:+.2f}%"],
                    ["波动范围", f"{p.volatility_range:.2f}"],
                ]
                
                if p.target_price:
                    product_data.append(["目标价格", f"{p.target_price:.2f}"])
                    status = "已达标" if p.current_price <= p.target_price else f"还需降{p.target_diff_percent:.1f}%"
                    product_data.append(["目标状态", status])
                
                product_table = Table(product_data, colWidths=[4*cm, 6*cm])
                product_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), chinese_font),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                ]))
                story.append(product_table)
                story.append(Spacer(1, 0.5*cm))
        
        # 生成PDF
        doc.build(story)
        self.logger.info(f"PDF报告已生成: {output_path}")
        return output_path
    
    def _generate_pdf_with_weasyprint(self, output_path: str, days_list: List[int]) -> str:
        """使用WeasyPrint生成PDF"""
        try:
            from weasyprint import HTML, CSS
        except ImportError:
            raise ImportError("weasyprint not available")
        
        # 生成HTML内容
        html_path = output_path.replace('.pdf', '_temp.html')
        self._generate_html_report(html_path, days_list)
        
        # 转换为PDF
        HTML(html_path).write_pdf(output_path)
        
        # 清理临时文件
        if os.path.exists(html_path):
            os.remove(html_path)
        
        return output_path
    
    def _generate_html_report(self, output_path: str, days_list: List[int]) -> str:
        """生成HTML报告作为PDF的备选"""
        # 先生成Markdown内容，然后转换为HTML
        md_path = output_path.replace('.html', '.md')
        self.generate_markdown_report(md_path, days_list)
        
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # 简单的Markdown到HTML转换
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>电商价格监控分析报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #7f8c8d; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4472C4; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #ecf0f1; padding: 20px; border-radius: 5px; }}
    </style>
</head>
<body>
    <pre>{md_content}</pre>
</body>
</html>"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"HTML报告已生成: {output_path}")
        return output_path
    
    def _fill_product_sheet(self, ws, products: List[TrendResult], title: str, 
                           header_font, header_fill, border, alignment_center, get_column_letter):
        """填充商品工作表"""
        headers = ["商品名称", "平台", "当前价格", "最低价", "最高价", "平均价", 
                   "涨跌额", "涨跌幅", "波动范围", "波动率", "趋势"]
        
        ws.append([title])
        ws.append(headers)
        
        # 设置表头样式
        for cell in ws[2]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = alignment_center
        
        for p in products:
            trend_text = "上涨" if p.trend_direction == "up" else "下跌" if p.trend_direction == "down" else "稳定"
            ws.append([
                p.product_name,
                p.platform,
                p.current_price,
                p.min_price,
                p.max_price,
                p.avg_price,
                p.price_change,
                f"{p.change_percent:.2f}%",
                p.volatility_range,
                f"{p.volatility_percent:.2f}%",
                trend_text
            ])
        
        # 设置列宽和边框
        for row in ws.iter_rows(min_row=3):
            for cell in row:
                cell.border = border
        
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 15
        ws.column_dimensions['A'].width = 40
    
    def _fill_target_sheet(self, ws, products: List[TrendResult], 
                          header_font, header_fill, border, alignment_center, get_column_letter):
        """填充目标价工作表"""
        headers = ["商品名称", "平台", "当前价格", "目标价格", "差额", "差额百分比"]
        
        ws.append(["达到目标价商品清单"])
        ws.append(headers)
        
        for cell in ws[2]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = alignment_center
        
        for p in products:
            diff = p.target_price - p.current_price
            diff_percent = (diff / p.target_price * 100) if p.target_price else 0
            ws.append([
                p.product_name,
                p.platform,
                p.current_price,
                p.target_price,
                diff,
                f"{diff_percent:.2f}%"
            ])
        
        for row in ws.iter_rows(min_row=3):
            for cell in row:
                cell.border = border
        
        ws.column_dimensions['A'].width = 40
    
    def _fill_all_products_sheet(self, ws, products: List[TrendResult], days_list: List[int],
                                header_font, header_fill, border, alignment_center, get_column_letter):
        """填充所有商品详情工作表（包含多时间段数据）"""
        primary_days = min(days_list)
        headers = ["商品名称", "平台", "当前价格"]
        
        # 为每个时间段添加列
        for days in days_list:
            headers.extend([f"{days}天最低价", f"{days}天最高价", f"{days}天涨跌幅"])
        
        headers.extend(["目标价", "趋势", "记录数"])
        
        ws.append(["所有商品详情"])
        ws.append(headers)
        
        for cell in ws[2]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = alignment_center
        
        for p in products:
            row = [p.product_name, p.platform, p.current_price]
            
            # 为每个时间段获取数据
            for days in days_list:
                result = self.analyzer.analyze_product(p.product_id, days)
                if result:
                    row.extend([result.min_price, result.max_price, f"{result.change_percent:.2f}%"])
                else:
                    row.extend(["N/A", "N/A", "N/A"])
            
            trend_text = "上涨" if p.trend_direction == "up" else "下跌" if p.trend_direction == "down" else "稳定"
            row.extend([
                p.target_price if p.target_price else "未设置",
                trend_text,
                p.record_count
            ])
            ws.append(row)
        
        for row in ws.iter_rows(min_row=3):
            for cell in row:
                cell.border = border
        
        ws.column_dimensions['A'].width = 40
    
    def _fill_key_products_sheet(self, ws, products: List[TrendResult], days_list: List[int],
                                header_font, header_fill, border, alignment_center, get_column_letter):
        """填充重点商品分析工作表"""
        ws.append(["重点商品趋势分析"])
        ws.append([])
        ws.append(["本部分展示价格波动最大、最值得关注的商品详细分析"])
        ws.append([])
        
        for i, p in enumerate(products, 1):
            ws.append([f"{i}. {p.product_name}"])
            ws.append(["属性", "数值"])
            
            # 基本信息
            ws.append(["平台", p.platform])
            ws.append(["商品ID", p.product_id])
            ws.append(["当前价格", p.current_price])
            
            # 多时间段对比
            for days in days_list:
                result = self.analyzer.analyze_product(p.product_id, days)
                if result:
                    ws.append([f"{days}天最低价", result.min_price])
                    ws.append([f"{days}天最高价", result.max_price])
                    ws.append([f"{days}天涨跌幅", f"{result.change_percent:.2f}%"])
            
            ws.append(["波动范围", p.volatility_range])
            ws.append(["波动率", f"{p.volatility_percent:.2f}%"])
            
            trend_text = "上涨" if p.trend_direction == "up" else "下跌" if p.trend_direction == "down" else "稳定"
            ws.append(["趋势方向", trend_text])
            
            if p.target_price:
                ws.append(["目标价格", p.target_price])
                status = "已达标" if p.current_price <= p.target_price else f"还需降{p.target_diff_percent:.1f}%"
                ws.append(["目标状态", status])
            
            ws.append([])  # 空行分隔
        
        # 设置样式
        for row in ws.iter_rows():
            for cell in row:
                cell.border = border
    
    def _generate_json_report(self, output_path: str, days_list: List[int]) -> str:
        """生成JSON格式的报告（作为Excel的备选）"""
        primary_days = min(days_list) if days_list else 7
        all_products = self.analyzer.analyze_all_products(primary_days)
        summaries = {days: self.analyzer.get_summary_stats(days) for days in (days_list or [7, 30])}
        
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "analysis_period_days": days_list or [7, 30],
            "summaries": summaries,
            "products": [
                {
                    "product_id": p.product_id,
                    "product_name": p.product_name,
                    "platform": p.platform,
                    "current_price": p.current_price,
                    "min_price": p.min_price,
                    "max_price": p.max_price,
                    "avg_price": p.avg_price,
                    "price_change": p.price_change,
                    "change_percent": p.change_percent,
                    "volatility_range": p.volatility_range,
                    "volatility_percent": p.volatility_percent,
                    "trend_direction": p.trend_direction,
                    "target_price": p.target_price,
                    "record_count": p.record_count
                }
                for p in all_products
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"JSON报告已生成: {output_path}")
        return output_path
    
    def generate_charts(self, output_path: str, days: int = 7) -> str:
        """生成价格趋势可视化图表"""
        try:
            import matplotlib
            matplotlib.use('Agg')  # 非交互式后端
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            # 设置中文字体支持
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
        except ImportError:
            self.logger.error("缺少matplotlib库，无法生成图表")
            return ""
        
        all_products = self.analyzer.analyze_all_products(days)
        
        if not all_products:
            self.logger.warning("没有数据可生成图表")
            return ""
        
        # 选择有价格历史的商品
        products_with_history = [p for p in all_products if len(p.price_history) >= 2]
        
        if not products_with_history:
            self.logger.warning("没有足够的价格历史数据生成图表")
            return ""
        
        # 限制图表数量，最多显示6个商品
        chart_products = products_with_history[:6]
        
        # 创建图表
        n_products = len(chart_products)
        n_cols = min(2, n_products)
        n_rows = (n_products + n_cols - 1) // n_cols
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4 * n_rows))
        if n_products == 1:
            axes = [axes]
        else:
            axes = axes.flatten() if n_rows > 1 else axes
        
        for idx, product in enumerate(chart_products):
            ax = axes[idx] if n_products > 1 else axes[0]
            
            # 解析日期和价格
            dates = []
            prices = []
            for h in product.price_history:
                try:
                    date_str = h.get('recorded_at', '')
                    if date_str:
                        date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        dates.append(date)
                        prices.append(h.get('price', 0))
                except (ValueError, TypeError):
                    continue
            
            if not dates:
                ax.text(0.5, 0.5, '无有效数据', ha='center', va='center', transform=ax.transAxes)
                continue
            
            # 绘制价格趋势线
            ax.plot(dates, prices, 'b-', linewidth=2, marker='o', markersize=4)
            
            # 添加最高/最低价格线
            ax.axhline(y=product.max_price, color='r', linestyle='--', alpha=0.5, label=f'最高: {product.max_price:.0f}')
            ax.axhline(y=product.min_price, color='g', linestyle='--', alpha=0.5, label=f'最低: {product.min_price:.0f}')
            
            # 设置标题和标签
            short_name = product.product_name[:20] + "..." if len(product.product_name) > 20 else product.product_name
            ax.set_title(f"{short_name}\n当前: {product.current_price:.0f} | 涨跌: {product.change_percent:+.1f}%", 
                        fontsize=10)
            ax.set_xlabel("日期", fontsize=8)
            ax.set_ylabel("价格", fontsize=8)
            
            # 格式化x轴日期
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//5)))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            ax.legend(loc='best', fontsize=7)
            ax.grid(True, alpha=0.3)
        
        # 隐藏多余的子图
        for idx in range(n_products, len(axes) if isinstance(axes, list) else 1):
            if isinstance(axes, list):
                axes[idx].set_visible(False)
        
        plt.suptitle(f"价格趋势分析 ({days}天)", fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        self.logger.info(f"图表已生成: {output_path}")
        return output_path
    
    def generate_comparison_charts(self, output_path: str, days_list: List[int] = None) -> str:
        """生成多时间段对比图表"""
        if days_list is None:
            days_list = [7, 30]
        
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            self.logger.error("缺少matplotlib库，无法生成图表")
            return ""
        
        summaries = {days: self.analyzer.get_summary_stats(days) for days in days_list}
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 图1: 价格变化分布对比（饼图）
        ax1 = axes[0, 0]
        labels = ['降价', '涨价', '稳定']
        primary_days = min(days_list)
        summary = summaries[primary_days]
        sizes = [summary['price_down_count'], summary['price_up_count'], summary['stable_count']]
        colors = ['#2ecc71', '#e74c3c', '#95a5a6']
        
        ax1.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax1.set_title(f'价格变化分布 ({primary_days}天)', fontsize=12, fontweight='bold')
        
        # 图2: 监控概览柱状图对比
        ax2 = axes[0, 1]
        x = range(len(days_list))
        width = 0.15
        
        metrics = ['total_products', 'price_down_count', 'price_up_count', 'target_reached_count']
        metric_labels = ['总商品', '降价', '涨价', '达标']
        colors_bar = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']
        
        for i, (metric, label, color) in enumerate(zip(metrics, metric_labels, colors_bar)):
            values = [summaries[days].get(metric, 0) for days in days_list]
            ax2.bar([xi + width * i for xi in x], values, width, label=label, color=color)
        
        ax2.set_xlabel('分析周期')
        ax2.set_ylabel('数量')
        ax2.set_title('监控概览对比', fontsize=12, fontweight='bold')
        ax2.set_xticks([xi + width * 1.5 for xi in x])
        ax2.set_xticklabels([f'{d}天' for d in days_list])
        ax2.legend()
        
        # 图3: 平均涨跌幅对比
        ax3 = axes[1, 0]
        avg_changes = [summaries[days].get('avg_change_percent', 0) for days in days_list]
        colors_change = ['#2ecc71' if v < 0 else '#e74c3c' if v > 0 else '#95a5a6' for v in avg_changes]
        
        bars = ax3.bar([f'{d}天' for d in days_list], avg_changes, color=colors_change)
        ax3.set_xlabel('分析周期')
        ax3.set_ylabel('平均涨跌幅 (%)')
        ax3.set_title('平均涨跌幅对比', fontsize=12, fontweight='bold')
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        
        # 在柱子上显示数值
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}%',
                    ha='center', va='bottom' if height > 0 else 'top')
        
        # 图4: 价格分布散点图（取前10个商品）
        ax4 = axes[1, 1]
        all_products = self.analyzer.analyze_all_products(primary_days)
        top_products = sorted(all_products, key=lambda x: abs(x.change_percent), reverse=True)[:10]
        
        if top_products:
            product_names = [p.product_name[:15] + "..." if len(p.product_name) > 15 else p.product_name for p in top_products]
            changes = [p.change_percent for p in top_products]
            colors_scatter = ['#2ecc71' if c < 0 else '#e74c3c' for c in changes]
            
            ax4.scatter(range(len(product_names)), changes, c=colors_scatter, s=100)
            ax4.set_xticks(range(len(product_names)))
            ax4.set_xticklabels(product_names, rotation=45, ha='right', fontsize=8)
            ax4.set_ylabel('涨跌幅 (%)')
            ax4.set_title('重点商品价格变动', fontsize=12, fontweight='bold')
            ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax4.grid(True, alpha=0.3)
        
        plt.suptitle(f"价格监控多维度对比分析", fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        self.logger.info(f"对比图表已生成: {output_path}")
        return output_path
    
    def generate_summary_chart(self, output_path: str, days: int = 7) -> str:
        """生成汇总统计图表"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            # 设置中文字体支持
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
        except ImportError:
            self.logger.error("缺少matplotlib库，无法生成图表")
            return ""
        
        summary = self.analyzer.get_summary_stats(days)
        
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        # 图1: 价格变化分布饼图
        labels = ['降价', '涨价', '稳定']
        sizes = [summary['price_down_count'], summary['price_up_count'], summary['stable_count']]
        colors = ['#2ecc71', '#e74c3c', '#95a5a6']
        
        axes[0].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        axes[0].set_title('价格变化分布', fontsize=12, fontweight='bold')
        
        # 图2: 监控概览柱状图
        categories = ['总商品', '降价', '涨价', '达标']
        values = [
            summary['total_products'],
            summary['price_down_count'],
            summary['price_up_count'],
            summary['target_reached_count']
        ]
        bar_colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']
        
        bars = axes[1].bar(categories, values, color=bar_colors)
        axes[1].set_title('监控概览', fontsize=12, fontweight='bold')
        axes[1].set_ylabel('数量')
        
        # 在柱子上显示数值
        for bar in bars:
            height = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height)}',
                        ha='center', va='bottom')
        
        plt.suptitle(f"价格监控汇总 ({days}天)", fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        self.logger.info(f"汇总图表已生成: {output_path}")
        return output_path


class JsonTrendAnalyzer(TrendAnalyzer):
    """支持JSON数据源的趋势分析器"""
    
    def __init__(self, json_path: str):
        self.logger = setup_logger(self.__class__.__name__)
        self.json_path = json_path
        self._products = None
        self._price_history = None
        self._load_data()
    
    def _load_data(self):
        """从JSON文件加载数据"""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 处理JSON数据格式
            if isinstance(data, list):
                self._products = {}
                self._price_history = {}
                for item in data:
                    product_id = item.get('id', item.get('product_id', 0))
                    self._products[product_id] = {
                        'id': product_id,
                        'name': item.get('name', item.get('product_name', 'Unknown')),
                        'platform': item.get('platform', 'unknown'),
                        'url': item.get('url', ''),
                        'target_price': item.get('target_price'),
                    }
                    
                    # 处理价格历史
                    history = item.get('price_history', [])
                    self._price_history[product_id] = history
            else:
                self._products = {}
                self._price_history = {}
            
            self.logger.info(f"从JSON加载了 {len(self._products)} 个商品")
        except Exception as e:
            self.logger.error(f"加载JSON数据失败: {e}")
            self._products = {}
            self._price_history = {}
    
    def get_all_products(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """获取所有商品"""
        return list(self._products.values())
    
    def get_price_history(self, product_id: int, days: int = None) -> List[Dict[str, Any]]:
        """获取价格历史"""
        history = self._price_history.get(product_id, [])
        
        if days and history:
            # 过滤最近N天的数据
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered_history = []
            for h in history:
                try:
                    recorded_at = h.get('recorded_at', '')
                    if recorded_at:
                        record_date = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                        if record_date >= cutoff_date:
                            filtered_history.append(h)
                except:
                    filtered_history.append(h)
            return filtered_history
        
        return history
    
    def analyze_all_products(self, days: int = 7) -> List[TrendResult]:
        """分析所有商品的价格趋势"""
        results = []
        
        for product_id in self._products.keys():
            result = self.analyze_product(product_id, days)
            if result:
                results.append(result)
        
        self.logger.info(f"完成 {len(results)} 个商品的趋势分析(JSON数据源)")
        return results
    
    def get_summary_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取汇总统计信息"""
        results = self.analyze_all_products(days)
        
        if not results:
            return {
                'total_products': 0,
                'price_down_count': 0,
                'price_up_count': 0,
                'stable_count': 0,
                'target_reached_count': 0,
                'avg_change_percent': 0,
                'analysis_period_days': days
            }
        
        down_count = sum(1 for r in results if r.trend_direction == 'down')
        up_count = sum(1 for r in results if r.trend_direction == 'up')
        stable_count = sum(1 for r in results if r.trend_direction == 'stable')
        target_reached = sum(1 for r in results if r.target_price and r.current_price <= r.target_price)
        
        avg_change = statistics.mean([r.change_percent for r in results])
        
        return {
            'total_products': len(results),
            'price_down_count': down_count,
            'price_up_count': up_count,
            'stable_count': stable_count,
            'target_reached_count': target_reached,
            'avg_change_percent': avg_change,
            'analysis_period_days': days
        }
    
    def analyze_product(self, product_id: int, days: int = 7) -> Optional[TrendResult]:
        """分析单个商品的价格趋势"""
        product = self._products.get(product_id)
        if not product:
            return None
        
        price_history = self.get_price_history(product_id, days)
        if not price_history:
            return None
        
        # 反转顺序，按时间正序排列
        price_history = list(reversed(price_history))
        
        # 计算统计数据
        prices = [h.get('price', 0) for h in price_history]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = statistics.mean(prices)
        current_price = prices[-1]
        
        # 计算涨跌幅
        first_price = prices[0]
        price_change = current_price - first_price
        change_percent = (price_change / first_price * 100) if first_price > 0 else 0
        
        # 确定趋势方向
        if change_percent > 2:
            trend_direction = "up"
        elif change_percent < -2:
            trend_direction = "down"
        else:
            trend_direction = "stable"
        
        # 计算波动范围
        volatility_range = max_price - min_price
        volatility_percent = (volatility_range / avg_price * 100) if avg_price > 0 else 0
        
        # 计算与目标价的差异
        target_price = product.get('target_price')
        target_diff = 0.0
        target_diff_percent = 0.0
        if target_price:
            target_diff = current_price - target_price
            target_diff_percent = (target_diff / target_price * 100) if target_price > 0 else 0
        
        return TrendResult(
            product_id=product_id,
            product_name=product['name'],
            platform=product['platform'],
            current_price=current_price,
            min_price=min_price,
            max_price=max_price,
            avg_price=avg_price,
            price_change=price_change,
            change_percent=change_percent,
            volatility_range=volatility_range,
            volatility_percent=volatility_percent,
            trend_direction=trend_direction,
            days=days,
            record_count=len(price_history),
            price_history=price_history,
            target_price=target_price,
            target_diff=target_diff,
            target_diff_percent=target_diff_percent
        )


@dataclass
class MergedProductInfo:
    """合并后的商品信息"""
    product_id: int
    name: str
    platform: str
    url: str
    target_price: Optional[float]
    price_history: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)  # 数据来源: 'sqlite', 'json'
    conflicts: List[Dict[str, Any]] = field(default_factory=list)  # 冲突信息
    current_price_sqlite: Optional[float] = None
    current_price_json: Optional[float] = None


class CombinedTrendAnalyzer:
    """联合数据源趋势分析器 - 同时读取SQLite和JSON数据源"""
    
    def __init__(self, db: Database = None, json_path: str = None):
        self.logger = setup_logger(self.__class__.__name__)
        self.db = db or Database()
        self.json_path = json_path or "data/exported_data.json"
        self.sqlite_analyzer = TrendAnalyzer(self.db)
        self.json_analyzer = None
        
        if os.path.exists(self.json_path):
            self.json_analyzer = JsonTrendAnalyzer(self.json_path)
        
        self._merged_products: Dict[int, MergedProductInfo] = {}
        self._merge_data()
    
    def _merge_data(self):
        """合并SQLite和JSON数据源的数据"""
        self.logger.info("开始合并SQLite和JSON数据源...")
        
        # 获取SQLite数据
        sqlite_products = {}
        try:
            sqlite_products_list = self.db.get_all_products()
            for p in sqlite_products_list:
                pid = p['id']
                sqlite_products[pid] = p
        except Exception as e:
            self.logger.error(f"读取SQLite数据失败: {e}")
        
        # 获取JSON数据
        json_products = {}
        if self.json_analyzer:
            for p in self.json_analyzer.get_all_products():
                pid = p.get('id', 0)
                if pid:
                    json_products[pid] = p
        
        # 合并数据
        all_ids = set(sqlite_products.keys()) | set(json_products.keys())
        
        for pid in all_ids:
            sqlite_p = sqlite_products.get(pid)
            json_p = json_products.get(pid)
            
            merged = MergedProductInfo(
                product_id=pid,
                name="",
                platform="",
                url="",
                target_price=None,
                sources=[]
            )
            
            conflicts = []
            
            # 处理SQLite数据
            if sqlite_p:
                merged.sources.append('sqlite')
                merged.name = sqlite_p.get('name', '')
                merged.platform = sqlite_p.get('platform', '')
                merged.url = sqlite_p.get('url', '')
                merged.target_price = sqlite_p.get('target_price')
                merged.current_price_sqlite = sqlite_p.get('current_price')
                
                # 获取SQLite价格历史
                try:
                    sqlite_history = self.db.get_price_history(pid, days=365)  # 获取所有历史
                    merged.price_history.extend(sqlite_history)
                except Exception as e:
                    self.logger.warning(f"获取SQLite价格历史失败 (商品ID: {pid}): {e}")
            
            # 处理JSON数据
            if json_p:
                merged.sources.append('json')
                if not merged.name:
                    merged.name = json_p.get('name', '')
                if not merged.platform:
                    merged.platform = json_p.get('platform', '')
                if not merged.url:
                    merged.url = json_p.get('url', '')
                if merged.target_price is None:
                    merged.target_price = json_p.get('target_price')
                
                # 获取JSON价格历史
                json_history = self.json_analyzer.get_price_history(pid, days=365)
                merged.current_price_json = json_p.get('current_price')
                
                # 合并价格历史，去重
                existing_times = {h.get('recorded_at') for h in merged.price_history}
                for h in json_history:
                    if h.get('recorded_at') not in existing_times:
                        merged.price_history.append(h)
                        existing_times.add(h.get('recorded_at'))
                
                # 检测冲突
                if sqlite_p and json_p:
                    sqlite_price = sqlite_p.get('current_price')
                    json_price = json_p.get('current_price')
                    if sqlite_price is not None and json_price is not None:
                        if abs(sqlite_price - json_price) > 0.01:  # 价格差异超过0.01视为冲突
                            conflicts.append({
                                'type': 'price_mismatch',
                                'sqlite_price': sqlite_price,
                                'json_price': json_price,
                                'diff': abs(sqlite_price - json_price),
                                'diff_percent': abs(sqlite_price - json_price) / sqlite_price * 100 if sqlite_price > 0 else 0
                            })
                    
                    # 检测名称冲突
                    sqlite_name = sqlite_p.get('name', '')
                    json_name = json_p.get('name', '')
                    if sqlite_name and json_name and sqlite_name != json_name:
                        conflicts.append({
                            'type': 'name_mismatch',
                            'sqlite_name': sqlite_name,
                            'json_name': json_name
                        })
            
            merged.conflicts = conflicts
            
            # 按时间排序价格历史
            merged.price_history.sort(key=lambda x: x.get('recorded_at', ''), reverse=True)
            
            self._merged_products[pid] = merged
        
        self.logger.info(f"数据合并完成: {len(self._merged_products)} 个商品")
        sqlite_only = sum(1 for m in self._merged_products.values() if m.sources == ['sqlite'])
        json_only = sum(1 for m in self._merged_products.values() if m.sources == ['json'])
        both_sources = sum(1 for m in self._merged_products.values() if len(m.sources) == 2)
        conflict_count = sum(1 for m in self._merged_products.values() if m.conflicts)
        
        self.logger.info(f"  - 仅SQLite: {sqlite_only}, 仅JSON: {json_only}, 双数据源: {both_sources}")
        self.logger.info(f"  - 存在冲突: {conflict_count}")
    
    def get_all_products(self) -> List[Dict[str, Any]]:
        """获取所有合并后的商品"""
        products = []
        for merged in self._merged_products.values():
            products.append({
                'id': merged.product_id,
                'name': merged.name,
                'platform': merged.platform,
                'url': merged.url,
                'target_price': merged.target_price,
                'sources': merged.sources,
                'conflicts': merged.conflicts,
                'current_price': merged.price_history[0].get('price') if merged.price_history else None
            })
        return products
    
    def get_price_history(self, product_id: int, days: int = None) -> List[Dict[str, Any]]:
        """获取合并后的价格历史"""
        merged = self._merged_products.get(product_id)
        if not merged:
            return []
        
        history = merged.price_history
        
        if days:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered = []
            for h in history:
                try:
                    recorded_at = h.get('recorded_at', '')
                    if recorded_at:
                        record_date = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                        if record_date >= cutoff_date:
                            filtered.append(h)
                except:
                    filtered.append(h)
            return filtered
        
        return history
    
    def analyze_product(self, product_id: int, days: int = 7) -> Optional[TrendResult]:
        """分析单个商品的价格趋势"""
        merged = self._merged_products.get(product_id)
        if not merged:
            return None
        
        price_history = self.get_price_history(product_id, days)
        if not price_history:
            return None
        
        # 反转顺序，按时间正序排列
        price_history = list(reversed(price_history))
        
        # 计算统计数据
        prices = [h.get('price', 0) for h in price_history]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = statistics.mean(prices)
        current_price = prices[-1]
        
        # 计算涨跌幅
        first_price = prices[0]
        price_change = current_price - first_price
        change_percent = (price_change / first_price * 100) if first_price > 0 else 0
        
        # 确定趋势方向
        if change_percent > 2:
            trend_direction = "up"
        elif change_percent < -2:
            trend_direction = "down"
        else:
            trend_direction = "stable"
        
        # 计算波动范围
        volatility_range = max_price - min_price
        volatility_percent = (volatility_range / avg_price * 100) if avg_price > 0 else 0
        
        # 计算与目标价的差异
        target_price = merged.target_price
        target_diff = 0.0
        target_diff_percent = 0.0
        if target_price:
            target_diff = current_price - target_price
            target_diff_percent = (target_diff / target_price * 100) if target_price > 0 else 0
        
        return TrendResult(
            product_id=product_id,
            product_name=merged.name,
            platform=merged.platform,
            current_price=current_price,
            min_price=min_price,
            max_price=max_price,
            avg_price=avg_price,
            price_change=price_change,
            change_percent=change_percent,
            volatility_range=volatility_range,
            volatility_percent=volatility_percent,
            trend_direction=trend_direction,
            days=days,
            record_count=len(price_history),
            price_history=price_history,
            target_price=target_price,
            target_diff=target_diff,
            target_diff_percent=target_diff_percent
        )
    
    def analyze_all_products(self, days: int = 7) -> List[TrendResult]:
        """分析所有商品的价格趋势"""
        results = []
        for product_id in self._merged_products.keys():
            result = self.analyze_product(product_id, days)
            if result:
                results.append(result)
        
        self.logger.info(f"完成 {len(results)} 个商品的联合趋势分析")
        return results
    
    def get_summary_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取汇总统计信息"""
        results = self.analyze_all_products(days)
        
        if not results:
            return {
                'total_products': 0,
                'price_down_count': 0,
                'price_up_count': 0,
                'stable_count': 0,
                'target_reached_count': 0,
                'avg_change_percent': 0,
                'analysis_period_days': days,
                'data_sources': {'sqlite_only': 0, 'json_only': 0, 'both': 0, 'conflicts': 0}
            }
        
        down_count = sum(1 for r in results if r.trend_direction == 'down')
        up_count = sum(1 for r in results if r.trend_direction == 'up')
        stable_count = sum(1 for r in results if r.trend_direction == 'stable')
        target_reached = sum(1 for r in results if r.target_price and r.current_price <= r.target_price)
        
        avg_change = statistics.mean([r.change_percent for r in results])
        
        # 统计数据源情况
        sqlite_only = sum(1 for m in self._merged_products.values() if m.sources == ['sqlite'])
        json_only = sum(1 for m in self._merged_products.values() if m.sources == ['json'])
        both_sources = sum(1 for m in self._merged_products.values() if len(m.sources) == 2)
        conflict_count = sum(1 for m in self._merged_products.values() if m.conflicts)
        
        return {
            'total_products': len(results),
            'price_down_count': down_count,
            'price_up_count': up_count,
            'stable_count': stable_count,
            'target_reached_count': target_reached,
            'avg_change_percent': avg_change,
            'analysis_period_days': days,
            'data_sources': {
                'sqlite_only': sqlite_only,
                'json_only': json_only,
                'both': both_sources,
                'conflicts': conflict_count
            }
        }
    
    def get_price_down_products(self, days: int = 7, min_percent: float = 0) -> List[TrendResult]:
        """获取降价商品列表"""
        results = self.analyze_all_products(days)
        down_products = [r for r in results if r.change_percent < -min_percent]
        return sorted(down_products, key=lambda x: x.change_percent)
    
    def get_price_up_products(self, days: int = 7, min_percent: float = 0) -> List[TrendResult]:
        """获取涨价商品列表"""
        results = self.analyze_all_products(days)
        up_products = [r for r in results if r.change_percent > min_percent]
        return sorted(up_products, key=lambda x: x.change_percent, reverse=True)
    
    def get_target_reached_products(self, days: int = 7) -> List[TrendResult]:
        """获取达到目标价格的商品"""
        results = self.analyze_all_products(days)
        reached_products = [r for r in results if r.target_price and r.current_price <= r.target_price]
        return reached_products
    
    def get_volatile_products(self, days: int = 7, min_volatility: float = 5.0) -> List[TrendResult]:
        """获取价格波动较大的商品"""
        results = self.analyze_all_products(days)
        volatile_products = [r for r in results if r.volatility_percent >= min_volatility]
        return sorted(volatile_products, key=lambda x: x.volatility_percent, reverse=True)
    
    def get_merged_product_info(self, product_id: int) -> Optional[MergedProductInfo]:
        """获取合并后的商品信息（包含数据来源和冲突信息）"""
        return self._merged_products.get(product_id)
    
    def get_all_conflicts(self) -> List[Dict[str, Any]]:
        """获取所有数据冲突"""
        conflicts = []
        for merged in self._merged_products.values():
            if merged.conflicts:
                conflicts.append({
                    'product_id': merged.product_id,
                    'product_name': merged.name,
                    'sources': merged.sources,
                    'conflicts': merged.conflicts
                })
        return conflicts
