import streamlit as st
import pandas as pd
import re

# 设置页面宽度和标题
st.set_page_config(page_title="LxU 广告全量分析看板", layout="wide")

st.title("📊 LxU 广告全量看板 (关键词明细 + 产品总计)")
st.markdown("特性：**斑马纹区分产品**、**绿色高亮总计行**、**1.1倍含税核算**、**支出占比分析**。")

# 1. 多文件批量上传
uploaded_files = st.file_uploader("批量上传 Coupang 广告报表 (CSV/Excel)", type=['csv', 'xlsx'], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            # 兼容韩文和中文 CSV 编码
            if file.name.endswith('.csv'):
                try:
                    df = pd.read_csv(file, encoding='cp949')
                except:
                    df = pd.read_csv(file, encoding='utf-8-sig')
            else:
                df = pd.read_excel(file)
            all_data.append(df)
        except Exception as e:
            st.error(f"读取文件 {file.name} 失败: {e}")

    if all_data:
        raw_df = pd.concat(all_data, ignore_index=True)

        # 2. 提取属性 (产品编号, 目标指标, 策略日期)
        def extract_info(row):
            # 获取 F列(索引5) 和 G列(索引6)
            camp_name = str(row.iloc[5]) if len(row) > 5 else ""
            grp_name = str(row.iloc[6]) if len(row) > 6 else ""
            full_text = f"{camp_name} {grp_name}"
            
            # 提取产品编号 (C001, C0001)
            p_code_match = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code_match.group(0).upper() if p_code_match else "未识别"
            
            # 提取目标指标 (方括号内的纯数字)
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = int(target_match.group(1)) if target_match else 0
            
            # 提取策略日期 (方括号内的点分隔日期)
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "汇总"
            
            return pd.Series([p_code, target_val, mod_date])

        raw_df[['产品编号', '目标指标', '策略日期']] = raw_df.apply(extract_info, axis=1)

        # 3. 清洗与归一化（合并非搜索区域）
        analysis_df = raw_df.copy()
        # 识别非搜索逻辑 (M列为空或L列含非搜索文字)
        mask_ns = (analysis_df.iloc[:, 12].isna()) | \
                  (analysis_df.iloc[:, 11].str.contains('비검색|非搜索', na=False)) | \
                  (analysis_df.iloc[:, 12].astype(str) == 'nan')
        
        # 统一关键词列 (M列索引12) 和展示版面 (L列索引11)
        analysis_df.iloc[:, 12] = analysis_df.iloc[:, 12].astype(str).str.strip().replace({'nan': '🤖 非搜索区域', '': '🤖 非搜索区域'})
        analysis_df.iloc[:, 11] = analysis_df.iloc[:, 11].astype(str).str.strip()
        
        # 强制归一化非搜索区域的所有维度
        analysis_df.loc[mask_ns, analysis_df.columns[12]] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, analysis_df.columns[11]] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '策略日期'] = '汇总'

        # 重命名核心列名 (对应索引: N=13, O=14, P=15, AD=29, AG=32)
        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面',
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '展示',
            analysis_df.columns[14]: '点击',
            analysis_df.columns[15]: '原支出',
            analysis_df.columns[29]: '销量',
            analysis_df.columns[32]: '销售额'
        })

        # 4. 聚合计算
        # a. 关键词明细级
        kw_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index()

        # b. 产品总计级
        product_sum = kw_summary.groupby('产品编号').agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        product_sum['展示版面'] = '📌 总计'
        product_sum['关键词'] = '📌 产品总计'
        product_sum['策略日期'] = 'TOTAL'

        # c. 合并并设置排序权重
        kw_summary['is_total'] = 0
        product_sum['is_total'] = 1
        combined_df = pd.concat([kw_summary, product_sum], ignore_index=True)
        # 排序：产品编号升序 -> 明细行在上，总计行在下 -> 支出降序
        combined_df = combined_df.sort_values(['产品编号', 'is_total', '原支出'], ascending=[True, True, False])

        # 5. 指标计算 (含税1.1倍)
        combined_df['真实支出'] = (combined_df['原支出'] * 1.1).round(0)
        combined_df['真实ROAS'] = (combined_df['销售额'] / combined_df['真实支出'] * 100).round(2)
        
        # 计算该产品内支出的百分比占比
        p_total_spend_map = product_sum.set_index('产品编号')['原支出'] * 1.1
        combined_df['支出占比'] = combined_df.apply(
            lambda x: (x['真实支出'] / p_total_spend_map[x['产品编号']] * 100) if x['is_total'] == 0 else 100.0, axis=1
        ).round(1)

        combined_df = combined_df.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 6. 界面展示与样式美化
        st.subheader("关键词全维度明细（含产品总计行）")
        
        # 斑马纹颜色映射
        unique_p = combined_df['产品编号'].unique()
        p_color_map = {p: '#f9f9f9' if i % 2 == 0 else '#ffffff' for i, p in enumerate(unique_p)}

        def apply_row_styles(row):
            """样式逻辑：总计行加粗变色，明细行斑马纹区分产品"""
            base_color = p_color_map[row['产品编号']]
            if row['is_total'] == 1:
                return ['background-color: #e8f4ea; font-weight: bold; border-top: 1px solid #ccc'] * len(row)
            return [f'background-color: {base_color}'] * len(row)

        # 渲染结果表格
        st.dataframe(
            combined_df.style.apply(apply_row_styles, axis=1),
            column_config={
                "is_total": None, # 隐藏辅助列
                "支出占比": st.column_config.NumberColumn(format="%.1f%%"),
                "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                "目标指标": st.column_config.NumberColumn(format="%d%%"),
                "真实支出": st.column_config.NumberColumn(format="₩%d"),
                "销售额": st.column_config.NumberColumn(format="₩%d")
            },
            hide_index=True,
            use_container_width=True
        )

        # 7. 下载按钮
        csv_data = combined_df.drop(columns=['is_total']).to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("📥 下载完整报告", csv_data, "LxU_Ads_Report.csv", "text/csv")

else:
    st.info("👋 请批量上传报表。建议文件名包含店铺名，方便后续扩展分析。")
