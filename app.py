import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="LxU 广告全维度看板", layout="wide")

st.title("🚀 LxU 广告全维度看板")
st.markdown("集成指标：**真实ROAS、真实CPC、点击率、转化率、目标指标(%)**。")

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

        # 3. 数据清洗重命名
        analysis_df = raw_df.copy()
        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示量', 
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '展示', 
            analysis_df.columns[14]: '点击量',
            analysis_df.columns[15]: '原支出', 
            analysis_df.columns[29]: '销量', 
            analysis_df.columns[32]: '销售额'
        })
        # 修正列名对齐
        analysis_df = analysis_df.rename(columns={'展示量': '维度', '展示': '展示量'})

        mask_ns = (analysis_df['关键词'].isna()) | \
                  (analysis_df['维度'].str.contains('비검색|非搜索', na=False)) | \
                  (analysis_df['关键词'].astype(str) == 'nan')
        
        analysis_df.loc[mask_ns, '关键词'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '维度'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '策略日期'] = '汇总'

        # 4. 指标计算
        def calculate_metrics(df):
            df['真实支出'] = (df['原支出'] * 1.1).round(0)
            df['真实ROAS'] = (df['销售额'] / df['真实支出'] * 100).round(2)
            df['真实CPC'] = (df['真实支出'] / df['点击量']).round(0)
            df['点击率'] = (df['点击量'] / df['展示量'] * 100).round(2)
            df['转化率'] = (df['销量'] / df['点击量'] * 100).round(2)
            return df.replace([float('inf'), -float('inf')], 0).fillna(0)

        kw_summary = analysis_df.groupby(['产品编号', '维度', '关键词', '目标指标', '策略日期']).agg({
            '展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index()
        kw_summary = calculate_metrics(kw_summary)

        product_totals = kw_summary.groupby('产品编号').agg({
            '展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        product_totals = calculate_metrics(product_totals)

        # --- 5. 找回顶部合计指标 (Metrics) ---
        t_spent = product_totals['真实支出'].sum()
        t_sales = product_totals['销售额'].sum()
        t_clicks = product_totals['点击量'].sum()
        t_views = product_totals['展示量'].sum()
        t_orders = product_totals['销量'].sum()

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("📦 总消耗", f"₩{t_spent:,.0f}")
        m2.metric("💰 总销售额", f"₩{t_sales:,.0f}")
        m3.metric("📈 ROAS", f"{(t_sales/t_spent*100):.2f}%" if t_spent>0 else "0%")
        m4.metric("🖱️ CPC", f"₩{(t_spent/t_clicks):.0f}" if t_clicks>0 else "0")
        m5.metric("🎯 点击率", f"{(t_clicks/t_views*100):.2f}%" if t_views>0 else "0%")
        m6.metric("🛒 转化率", f"{(t_orders/t_clicks*100):.2f}%" if t_clicks>0 else "0%")

        # --- 6. 侧边栏筛选 ---
        st.sidebar.header("📊 盈亏筛选器")
        status_filter = st.sidebar.radio("选择范围：", ["全部", "盈利", "亏损"])
        
        valid_p = product_totals['产品编号'].tolist()
        if status_filter == "盈利":
            valid_p = product_totals[product_totals['真实ROAS'] >= product_totals['目标指标']]['产品编号'].tolist()
        elif status_filter == "亏损":
            valid_p = product_totals[product_totals['真实ROAS'] < product_totals['目标指标']]['产品编号'].tolist()

        # --- 7. 样式逻辑 (恢复浅绿色) ---
        unique_p = product_totals['产品编号'].unique()
        p_color_map = {p: '#f9f9f9' if i % 2 == 0 else '#ffffff' for i, p in enumerate(unique_p)}

        def apply_lxu_style(row, is_tab1=True):
            p_code = row['产品编号']
            base_color = p_color_map.get(p_code, '#ffffff')
            is_total = (row['维度'] == '📌 产品总计') if is_tab1 else (row['sort_weight'] == 2)
            is_ns = (row['维度'] == '🤖 非搜索区域') if is_tab1 else (row['sort_weight'] == 0)
            
            styles = []
            for col_name in row.index:
                cell_style = f'background-color: {base_color}'
                if is_total:
                    # 恢复总计行浅绿色背景
                    cell_style = 'background-color: #e8f4ea; font-weight: bold; border-top: 1px solid #ccc'
                    # 达标则加深
                    if col_name == '真实ROAS' and row['目标指标'] > 0 and row['真实ROAS'] >= row['目标指标']:
                        cell_style = 'background-color: #2e7d32; color: #ffffff; font-weight: bold'
                elif is_ns:
                    cell_style = f'background-color: {base_color}; color: #0056b3; font-weight: 500'
                
                # 普通行达标高亮
                if not is_total and col_name == '真实ROAS' and row['目标指标'] > 0 and row['真实ROAS'] >= row['目标指标']:
                    cell_style += '; background-color: #c6efce; color: #006100'
                styles.append(cell_style)
            return styles

        p_spend_map = product_totals.set_index('产品编号')['真实支出']

        # --- 8. 渲染表格 ---
        st.divider()
        tab1, tab2 = st.tabs(["🎯 产品对比看板", "📄 关键词明细表"])

        with tab1:
            kw_f = kw_summary[kw_summary['产品编号'].isin(valid_p)].copy()
            kw_f['维度'] = kw_f['关键词'].apply(lambda x: '🤖 非搜索区域' if '非搜索' in x else '🔎 搜索区域')
            area_df = kw_f.groupby(['产品编号', '维度']).agg({'展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'}).reset_index()
            area_df = calculate_metrics(area_df)
            area_df['支出占比'] = area_df.apply(lambda x: (x['真实支出']/p_spend_map[x['产品编号']]*100) if x['产品编号'] in p_spend_map else 0, axis=1).round(1)
            p_sub = product_totals[product_totals['产品编号'].isin(valid_p)].copy()
            p_sub['维度'], p_sub['支出占比'] = '📌 产品总计', 100.0
            t1_df = pd.concat([area_df, p_sub], ignore_index=True).sort_values(['产品编号', '维度'], ascending=[True, False])
            st.dataframe(t1_df.style.apply(lambda r: apply_lxu_style(r, True), axis=1), use_container_width=True, hide_index=True)

        with tab2:
            kw_f['sort_weight'] = kw_f['关键词'].apply(lambda x: 0 if '非搜索' in x else 1)
            det_sub = p_sub.rename(columns={'维度': '关键词'})
            det_sub['策略日期'], det_sub['sort_weight'] = 'TOTAL', 2
            t2_df = pd.concat([kw_f, det_sub], ignore_index=True).sort_values(['产品编号', 'sort_weight', '真实支出'], ascending=[True, True, False])
            t2_df['支出占比'] = t2_df.apply(lambda x: (x['真实支出']/p_spend_map[x['产品编号']]*100) if x['sort_weight'] != 2 else 100.0, axis=1).round(1)
            st.dataframe(t2_df.style.apply(lambda r: apply_lxu_style(r, False), axis=1), use_container_width=True, hide_index=True, height=800)

        # 9. Excel 导出 (保持视觉一致)
        def to_excel_lxu(df1, df2):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                wb = writer.book
                total_bg = wb.add_format({'bg_color': '#e8f4ea', 'bold': True})
                success_bg = wb.add_format({'bg_color': '#2e7d32', 'font_color': '#ffffff', 'bold': True})
                
                df1.to_excel(writer, sheet_name='Sheet1_对比汇总', index=False)
                ws1 = writer.sheets['Sheet1_对比汇总']
                for r_idx, (roas, target, dim) in enumerate(zip(df1['真实ROAS'], df1['目标指标'], df1['维度'])):
                    if dim == '📌 产品总计':
                        ws1.set_row(r_idx+1, None, success_bg if (target > 0 and roas >= target) else total_bg)

                df2.drop(columns=['sort_weight'], errors='ignore').to_excel(writer, sheet_name='Sheet2_明细', index=False)
                ws2 = writer.sheets['Sheet2_明细']
                for r_idx, (roas, target, weight) in enumerate(zip(df2['真实ROAS'], df2['目标指标'], df2['sort_weight'])):
                    if weight == 2:
                        ws2.set_row(r_idx+1, None, success_bg if (target > 0 and roas >= target) else total_bg)
            return output.getvalue()

        st.sidebar.download_button("📥 下载 Excel 报告", to_excel_lxu(t1_df, t2_df), "LxU_Ads.xlsx")
else:
    st.info("👋 请上传报表。")
