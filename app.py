import streamlit as st
import pandas as pd
import re
import plotly.express as px

st.set_page_config(page_title="LxU 广告智能决策看板", layout="wide")

st.title("🚀 LxU 广告智能决策看板")

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

        # --- 2. 属性提取引擎 ---
        def extract_info(row):
            camp_name, grp_name = str(row.iloc[5]), str(row.iloc[6])
            full_text = f"{camp_name} {grp_name}"
            p_code = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code_match.group(0).upper() if (p_code_match := p_code) else "未识别"
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = int(target_match.group(1)) if target_match else 0
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "汇总"
            return pd.Series([p_code, target_val, mod_date])

        raw_df[['产品编号', '目标指标', '策略日期']] = raw_df.apply(extract_info, axis=1)

        # --- 3. 数据清洗与对齐 ---
        analysis_df = raw_df.copy()
        mask_ns = (analysis_df.iloc[:, 12].isna()) | \
                  (analysis_df.iloc[:, 11].str.contains('비검색|非搜索', na=False)) | \
                  (analysis_df.iloc[:, 12].astype(str) == 'nan')
        
        analysis_df.iloc[:, 12] = analysis_df.iloc[:, 12].astype(str).str.strip().replace({'nan': '🤖 非搜索区域', '': '🤖 非搜索区域'})
        analysis_df.iloc[:, 11] = analysis_df.iloc[:, 11].astype(str).str.strip()
        analysis_df.loc[mask_ns, analysis_df.columns[12]] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, analysis_df.columns[11]] = '🤖 非搜索区域'

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[13]: '展示', analysis_df.columns[14]: '点击',
            analysis_df.columns[15]: '原支出', analysis_df.columns[29]: '销量', analysis_df.columns[32]: '销售额'
        })

        # --- 4. 核心计算逻辑 ---
        # 关键词级明细
        kw_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index()

        # 产品级汇总 (用于图表和总计行)
        product_totals = kw_summary.groupby('产品编号').agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        product_totals['真实支出'] = (product_totals['原支出'] * 1.1).round(0)
        product_totals['真实ROAS'] = (product_totals['销售额'] / product_totals['真实支出'] * 100).round(2)

        # --- 5. 顶层全局大盘 (表格外部分析) ---
        total_spent = product_totals['真实支出'].sum()
        total_sales = product_totals['销售额'].sum()
        avg_roas = (total_sales / total_spent * 100) if total_spent > 0 else 0

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("📦 全局总消耗 (含税)", f"₩{total_spent:,.0f}")
        col_m2.metric("💰 全局总销售额", f"₩{total_sales:,.0f}")
        col_m3.metric("📈 平均 ROAS", f"{avg_roas:.2f}%")

        # 统计图表：各产品 ROAS 表现排名
        fig_roas = px.bar(product_totals.sort_values('真实ROAS', ascending=False), 
                         x='产品编号', y='真实ROAS', color='真实ROAS',
                         title="各产品真实 ROAS 排名 (含税)",
                         labels={'真实ROAS': 'ROAS (%)'},
                         color_continuous_scale='RdYlGn')
        st.plotly_chart(fig_roas, use_container_width=True)

        # --- 6. 详细分析表 (Tabs 布局) ---
        st.divider()
        tab1, tab2 = st.tabs(["🎯 产品对比看板 (汇总)", "📄 关键词详细明细 (下钻)"])

        # 样式辅助数据
        unique_p = product_totals['产品编号'].unique()
        p_color_map = {p: '#f9f9f9' if i % 2 == 0 else '#ffffff' for i, p in enumerate(unique_p)}

        def apply_styles(row, weight_val):
            base_color = p_color_map[row['产品编号']]
            if weight_val == 'total': # 总计行
                return ['background-color: #e8f4ea; font-weight: bold; border-top: 2px solid #ccc'] * len(row)
            if weight_val == 'non_search': # 非搜索行
                return [f'background-color: {base_color}; color: #0056b3; font-weight: 500'] * len(row)
            return [f'background-color: {base_color}'] * len(row)

        with tab1:
            # 组装看板数据
            kw_summary['维度'] = kw_summary['关键词'].apply(lambda x: '🤖 非搜索区域' if '非搜索' in x else '🔎 搜索区域')
            area_summary = kw_summary.groupby(['产品编号', '维度']).agg({
                '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销售额': 'sum', '目标指标': 'max'
            }).reset_index()
            area_summary['真实支出'] = (area_summary['原支出'] * 1.1).round(0)
            
            p_sub_totals = product_totals.copy()
            p_sub_totals['维度'] = '📌 产品总计'
            
            compare_df = pd.concat([area_summary, p_sub_totals], ignore_index=True).sort_values(['产品编号', '维度'], ascending=[True, False])
            compare_df['真实ROAS'] = (compare_df['销售额'] / compare_df['真实支出'] * 100).round(2)

            st.dataframe(
                compare_df.style.apply(lambda r: apply_styles(r, 'total' if r['维度'] == '📌 产品总计' else 'normal'), axis=1),
                column_config={"真实ROAS": st.column_config.NumberColumn(format="%.2f%%"), "真实支出": st.column_config.NumberColumn(format="₩%d"), "销售额": st.column_config.NumberColumn(format="₩%d")},
                hide_index=True, use_container_width=True, height=500
            )

        with tab2:
            # 组装明细数据
            kw_summary['sort_weight'] = kw_summary['关键词'].apply(lambda x: 0 if '非搜索' in x else 1)
            det_totals = p_sub_totals.rename(columns={'维度': '关键词'})
            det_totals['展示版面'] = '📌 总计'
            det_totals['策略日期'] = 'TOTAL'
            det_totals['sort_weight'] = 2

            detailed_final = pd.concat([kw_summary, det_totals], ignore_index=True)
            detailed_final = detailed_final.sort_values(['产品编号', 'sort_weight', '原支出'], ascending=[True, True, False])
            detailed_final['真实支出'] = (detailed_final['原支出'] * 1.1).round(0)
            detailed_final['真实ROAS'] = (detailed_final['销售额'] / detailed_final['真实支出'] * 100).round(2)
            
            p_spend_map = product_totals.set_index('产品编号')['真实支出']
            detailed_final['支出占比'] = detailed_final.apply(lambda x: (x['真实支出'] / p_spend_map[x['产品编号']] * 100) if x['sort_weight'] != 2 else 100.0, axis=1).round(1)

            st.dataframe(
                detailed_final.style.apply(lambda r: apply_styles(r, 'total' if r['sort_weight']==2 else ('non_search' if r['sort_weight']==0 else 'normal')), axis=1),
                column_config={"sort_weight": None, "维度": None, "支出占比": st.column_config.NumberColumn(format="%.1f%%"), "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"), "真实支出": st.column_config.NumberColumn(format="₩%d")},
                hide_index=True, use_container_width=True, height=900
            )

        # 侧边栏下载
        csv_data = detailed_final.drop(columns=['sort_weight', '维度']).to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("📥 下载完整报告", csv_data, "LxU_Full_Analysis.csv", "text/csv")
else:
    st.info("👋 请批量上传报表。")
