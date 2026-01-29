# 📊 LxU Coupang 广告报表分析助手

这是一个基于 Python 和 Streamlit 开发的内部工具，专门用于解析 Coupang 广告后台导出的数据报表。

## 🚀 功能特点
* **多账号兼容**：支持上传多个 CSV/Excel 报表进行汇总。
* **核心指标自动化**：自动计算 ROAS、CTR、CPC 及各 SKU 表现。
* **可视化看板**：通过气泡图和柱状图直观展示消耗与产出比。
* **数据安全**：代码托管于 GitHub，通过 Streamlit Cloud 私有部署。

## 🛠 如何使用
1. **导出报表**：从 Coupang 广告管理后台导出特定日期的 `CSV` 或 `Excel` 文件。
2. **上传文件**：打开本应用网页，将文件拖入上传区域。
3. **查看分析**：左侧边栏可筛选特定账号或日期，中间区域查看可视化统计。

## 📦 技术栈
* Python 3.9+
* Streamlit (UI 框架)
* Pandas (数据处理)
* Plotly (交互式绘图)

---
*Developed by LxU Team*
