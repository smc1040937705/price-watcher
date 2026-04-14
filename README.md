# Price Watcher - 电商价格监控系统

电商价格监控爬虫与数据分析工具，支持多平台商品价格自动监控、变动检测、历史趋势追踪。

## ✨ 功能特性

### 🕷️ 多平台爬虫引擎
- ✅ 支持京东、淘宝、天猫等主流电商平台
- ✅ 自动识别平台类型
- ✅ User-Agent 随机伪装
- ✅ 失败自动重试 + 随机延时反爬
- ✅ 商品名称、价格、图片、库存信息提取

### 💾 数据持久化存储
- ✅ SQLite 轻量数据库，免安装
- ✅ 完整价格历史记录（带时间戳）
- ✅ 商品基础信息管理
- ✅ 最低价、最高价、均价统计查询
- ✅ 数据一键导出为 JSON 格式

### 🔔 智能价格变动检测
- ✅ 自动检测涨价/降价
- ✅ 设置目标提醒价
- ✅ 优惠商品筛选（降价 X% 以上）
- ✅ 监控状态汇总统计
- ✅ 精确计算涨跌幅百分比

### 📊 完整的命令行工具
- ✅ 添加/删除监控商品
- ✅ 批量刷新所有商品价格
- ✅ 查看商品详情和价格历史
- ✅ 查看所有监控商品列表
- ✅ 导出标准化数据供分析使用

## 🚀 快速开始

### 环境要求
- Python 3.8+
- pip 包管理器

### 安装依赖
```bash
pip install -r requirements.txt
```

### 基础使用

#### 1. 添加商品监控
```bash
python cli.py add "https://item.jd.com/100065243343.html" --target-price 8500
```

#### 2. 查看所有监控商品
```bash
python cli.py list
```

#### 3. 查看商品详情和价格历史
```bash
python cli.py detail 1
```

#### 4. 刷新所有商品价格
```bash
python cli.py refresh
```

#### 5. 查看降价商品
```bash
# 查看降价超过 10% 的商品
python cli.py bargains --discount 10
```

#### 6. 查看监控状态
```bash
python cli.py status
```

#### 7. 导出数据
```bash
python cli.py export-data
```

## 📁 项目结构

```
price-watcher/
├── price_monitor/
│   ├── __init__.py          # 模块导出入口
│   ├── config.py            # 配置加载器
│   ├── logger.py            # 彩色日志系统
│   ├── spider/              # 多平台爬虫引擎
│   ├── storage/             # SQLite 数据存储
│   ├── manager/             # 商品管理模块
│   └── detector/            # 价格变动检测
├── cli.py                   # 命令行入口
├── config.yaml              # 系统配置文件
├── requirements.txt         # Python 依赖
└── data/
    ├── price_monitor.db     # SQLite 数据库
    └── exported_data.json   # 导出的 JSON 数据
```

## 🛠️ 技术栈

| 功能 | 技术选型 |
|------|----------|
| 网络请求 | `requests` + `fake-useragent` |
| 页面解析 | `BeautifulSoup4` + `lxml` |
| 数据存储 | `SQLite3` |
| 配置管理 | `PyYAML` |
| 命令行交互 | `Click` |
| 日志系统 | `colorlog` |
| 数据展示 | `tabulate` |

## 💡 使用示例

### 示例输出 - 商品列表
```
  ID  商品名称                           平台    当前价格    最低价    最高价    目标价
----  ---------------------------------  ------  ----------  --------  --------  --------
   1  Apple iPhone 15 Pro Max 256GB ...  jd      ¥8999.00    ¥8799.00  ¥9999.00  ¥8500.00

共 1 个监控商品
```

### 示例输出 - 价格变动检测
```
📊 监控状态摘要
   监控商品总数: 1
   价格变动商品: 1
   降价: 1 个
   涨价: 0 个
   达到目标价: 0 个

2026-04-14 20:02:41,640 - PriceChangeDetector - INFO - 降价检测: Apple iPhone 15 Pro Max - ¥9099.0 → ¥8999.0, 降了 1.1%
```

## 🔧 配置说明

编辑 `config.yaml` 自定义爬虫行为：

```yaml
spider:
  request_timeout: 30        # 请求超时
  retry_times: 3             # 重试次数
  retry_delay: 5             # 重试延迟
  random_delay_min: 1        # 最小随机延时
  random_delay_max: 3        # 最大随机延时
```

## 🎯 适用场景

- 🛒 个人网购价格监控，入手最佳时机提醒
- 📊 电商竞品价格追踪与分析
- 💹 商品价格波动趋势研究
- 🔔 降价优惠自动提醒

---

**爬虫 + 数据自动化处理 - 典型应用案例**
