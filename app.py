import streamlit as st
import pandas as pd
import re
import plotly.express as px

st.set_page_config(page_title="LxU 广告全维度看板", layout="wide")

st.title("🚀 LxU 广告全维度看板 (达标高亮版)")
st.markdown("已优化：**目标指标**与**真实ROAS**相邻显示，且达标单元格自动**背景变绿**。")

# 1. 文件上传
uploaded_files = st.file_uploader("批量上传广告报表", type=['csv', 'xlsx'], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
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

        # 2. 属性提取引擎
        def extract_info(row):
            camp_name = str(row.iloc[5]) if len(row) > 5 else ""
            grp_name = str(row.iloc[6]) if len(row) > 6 else ""
            full_text = f"{camp_name} {grp_name}"
            p_code = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code.group(0).upper() if p_code else "未识别"
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = int(target_match.group(1)) if target_match else 0
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "汇总"
            return pd.Series([p_code, target_val, mod_date], index=['产品编号', '目标指标', '策略日期'])

        extracted_cols = raw_df.apply(extract_info, axis=1)
        raw_df = pd.concat([raw_df, extracted_cols], axis=1)

        # 3. 数据清洗
        analysis_df = raw_df.copy()
        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面', 
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '展示量', 
            analysis_df.columns[14]: '点击量',
            analysis_df.columns[15]: '原支出', 
            analysis_df.columns[29]: '销量', 
            analysis_df.columns[32]: '销售额'
        })

        mask_ns = (analysis_df['关键词'].isna()) | \
                  (analysis_df['展示版面'].str.contains('비검색|非搜索', na=False)) | \
                  (analysis_df['关键词'].astype(str) == 'nan')
        
        analysis_df.loc[mask_ns, '关键词'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '展示版面'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '策略日期'] = '汇总'

        # 4. 聚合与指标计算
        def calculate_metrics(df):
            df['真实支出'] = (df['原支出'] * 1.1).round(0)
            df['真实ROAS'] = (df['销售额'] / df['真实支出'] * 100).round(2)
            df['真实CPC'] = (df['真实支出'] / df['点击量']).round(0)
            df['点击率'] = (df['点击量'] / df['展示量'] * 100).round(2)
            df['转化率'] = (df['销量'] / df['点击量'] * 100).round(2)
            return df.replace([float('inf'), -float('inf')], 0).fillna(0)

        kw_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index()
        kw_summary = calculate_metrics(kw_summary)

        product_totals = kw_summary.groupby('产品编号').agg({
            '展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        product_totals = calculate_metrics(product_totals)

        # --- 5. 样式函数 (支持 ROAS 达标高亮) ---
        unique_p = product_totals['产品编号'].unique()
        p_color_map = {p: '#f9f9f9' if i % 2 == 0 else '#ffffff' for i, p in enumerate(unique_p)}

        def apply_complex_styles(row, mode='detailed'):
            p_code = row['产品编号']
            base_color = p_color_map.get(p_code, '#ffffff')
            is_total = (row['维度'] == '📌 产品总计') if mode=='area' else (row['sort_weight'] == 2)
            is_ns = (row['维度'] == '🤖 非搜索区域') if mode=='area' else (row['sort_weight'] == 0)
            
            styles = []
            for col_name in row.index:
                cell_style = f'background-color: {base_color}'
                if is_total:
                    cell_style = 'background-color: #e8f4ea; font-weight: bold; border-top: 2px solid #ccc'
                elif is_ns:
                    cell_style = f'background-color: {base_color}; color: #0056b3; font-weight: 500'
                
                # 达标高亮：当真实ROAS >= 目标指标且目标指标不为0时，单元格变绿
                if col_name == '真实ROAS' and row['目标指标'] > 0 and row['真实ROAS'] >= row['目标指标']:
                    cell_style += '; background-color: #c6efce; color: #006100' # 浅绿背景+深绿文字
                
                styles.append(cell_style)
            return styles

        # --- 6. 详细分析表 ---
        st.divider()
        tab1, tab2 = st.tabs(["🎯 产品对比看板 (汇总)", "📄 关键词详细明细 (下钻)"])

        with tab1:
            kw_summary['维度'] = kw_summary['关键词'].apply(lambda x: '🤖 非搜索区域' if '非搜索' in x else '🔎 搜索区域')
            area_df = kw_summary.groupby(['产品编号', '维度']).agg({'展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'}).reset_index()
            area_df = calculate_metrics(area_df)
            p_sub = product_totals.copy(); p_sub['维度'] = '📌 产品总计'
            compare_df = pd.concat([area_df, p_sub], ignore_index=True).sort_values(['产品编号', '维度'], ascending=[True, False])
            
            st.dataframe(compare_df.style.apply(lambda r: apply_complex_styles(r, 'area'), axis=1), 
                         column_order=("产品编号", "维度", "目标指标", "真实ROAS", "真实支出", "销售额", "真实CPC", "点击率", "转化率"),
                         column_config={
                             "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"), 
                             "目标指标": st.column_config.NumberColumn(format="%d%%"),
                             "真实支出": st.column_config.NumberColumn(format="₩%d"), 
                             "销售额": st.column_config.NumberColumn(format="₩%d")
                         },
                         hide_index=True, use_container_width=True)

        with tab2:
            kw_summary['sort_weight'] = kw_summary['关键词'].apply(lambda x: 0 if '非搜索' in x else '🤖 非搜索区域' if '非搜索' in x else 1)
            det_sub = p_sub.rename(columns={'维度': '关键词'})
            det_sub['展示版面'], det_sub['策略日期'], det_sub['sort_weight'] = '📌 总计', 'TOTAL', 2
            
            detailed_final = pd.concat([kw_summary, det_sub], ignore_index=True)
            detailed_final = detailed_final.sort_values(['产品编号', 'sort_weight', '真实支出'], ascending=[True, True, False])
            
            p_spend_map = product_totals.set_index('产品编号')['真实支出']
            detailed_final['支出占比'] = detailed_final.apply(lambda x: (x['真实支出'] / p_spend_map[x['产品编号']] * 100) if x['sort_weight'] != 2 else 100.0, axis=1).round(1)

            st.dataframe(
                detailed_final.style.apply(lambda r: apply_complex_styles(r, 'detailed'), axis=1),
                column_order=("产品编号", "展示版面", "关键词", "策略日期", "目标指标", "真实ROAS", "真实支出", "销售额", "真实CPC", "点击率", "转化率", "支出占比"),
                column_config={
                    "sort_weight": None, "维度": None, 
                    "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                    "目标指标": st.column_config.NumberColumn(format="%d%%"),
                    "真实支出": st.column_config.NumberColumn(format="₩%d"), 
                    "支出占比": st.column_config.NumberColumn(format="%.1f%%")
                },
                hide_index=True, use_container_width=True, height=1000
            )

        csv_data = detailed_final.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("📥 下载完整报告", csv_data, "LxU_Full_Report.csv", "text/csv")
else:
    st.info("👋 请上传报表。")
