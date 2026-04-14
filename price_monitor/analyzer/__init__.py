"""
价格分析模块 - 提供价格趋势分析和报告生成功能
"""

from .trend_analyzer import TrendAnalyzer, TrendResult
from .report_generator import (
    ReportGenerator, 
    JsonTrendAnalyzer, 
    CombinedTrendAnalyzer,
    MergedProductInfo
)

__all__ = [
    'TrendAnalyzer', 
    'TrendResult', 
    'ReportGenerator', 
    'JsonTrendAnalyzer',
    'CombinedTrendAnalyzer',
    'MergedProductInfo'
]
