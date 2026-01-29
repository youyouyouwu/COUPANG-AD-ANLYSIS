import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告智能决策看板", layout="wide")

# --- 界面头部 ---
st.title("🚀 LxU 广告智能决策看板")
st.markdown("已集成：全维度对比、长屏预览、产品级穿透分析。")

# 1. 文件上传
uploaded_files = st.file_uploader("批量上传广告报表", type=['csv', 'xlsx'], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            df = pd.read_csv(file, encoding='cp949') if file.name.endswith('.csv') else pd.read_excel(file)
            all_data.append(df)
        except:
            df = pd.read_csv(file, encoding='utf-8-sig')
            all_data.append(df)

    if all_data:
        raw_df = pd.concat(all_data, ignore_index=True)

        # --- 2. 数据处理引擎 ---
        def extract_info(row):
            camp_name, grp_name = str(row.iloc[5]), str(row.iloc[6])
            full_text = f"{camp_name} {grp_name}"
            p_code = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code.group(0).upper() if p_code else "未识别"
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = int(target_match.group(1)) if target_match else 0
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "汇总"
            return pd.Series([p_code, target_val, mod_date])

        raw_df[['产品编号', '目标指标', '策略日期']] = raw_df.apply(extract_info, axis=1)

        # 数据清洗：合并非搜索
        analysis_df = raw_df.copy()
        mask_ns = (analysis_df.iloc[:, 12].isna()) | (analysis_df.iloc[:, 11].str.contains('비검색|非搜索', na=False)) | (analysis_df.iloc[:, 12].astype(str) == 'nan')
        
        analysis_df['展示版面'] = analysis_df.iloc[:, 11].astype(str).str.strip()
        analysis_df['关键词'] = analysis_df.iloc[:, 12].astype(str).str.strip()
        
        analysis_df.loc[mask_ns, '展示版面'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '关键词'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '策略日期'] = '汇总'

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[13]: '展示', analysis_df.columns[14]: '点击',
            analysis_df.columns[15]: '原支出', analysis_df.columns[29]: '销量', analysis_df.columns[32]: '销售额'
        })

        # --- 3. 聚合计算 ---
        # 关键词级明细
        kw_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index().sort_values(['产品编号', '原支出'], ascending=[True, False])

        kw_summary['真实支出'] = (kw_summary['原支出'] * 1.1).round(0)
        kw_summary['真实ROAS'] = (kw_summary['销售额'] / kw_summary['真实支出'] * 100).round(2)
        kw_summary['支出占比'] = (kw_summary['真实支出'] / kw_summary.groupby('产品编号')['真实支出'].transform('sum') * 100).round(1)
        kw_summary = kw_summary.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 产品看板级
        kw_summary['维度分类'] = kw_summary['关键词'].apply(lambda x: '🤖 非搜索区域' if '非搜索' in x else '🔎 搜索区域')
        area_summary = kw_summary.groupby(['产品编号', '维度分类']).agg({
            '展示': 'sum', '点击': 'sum', '真实支出': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()

        product_totals = area_summary.groupby('产品编号').agg({
            '展示': 'sum', '点击': 'sum', '真实支出': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        product_totals['维度分类'] = '📌 产品总计'

        final_compare = pd.concat([area_summary, product_totals], ignore_index=True).sort_values(['产品编号', '维度分类'], ascending=[True, False])
        final_compare['真实ROAS'] = (final_compare['销售额'] / final_compare['真实支出'] * 100).round(2)

        # --- 4. 侧边栏交互组件 ---
        st.sidebar.header("🔍 数据筛选中心")
        search_query = st.sidebar.text_input("搜索产品编号 (如 C001)", "").upper()
        
        roas_filter = st.sidebar.slider("最小真实 ROAS (%)", 0, 1000, 0)
        
        # 应用过滤
        if search_query:
            kw_summary = kw_summary[kw_summary['产品编号'].str.contains(search_query)]
            final_compare = final_compare[final_compare['产品编号'].str.contains(search_query)]
        
        # --- 5. 顶层数据卡片 ---
        total_spent = kw_summary['真实支出'].sum()
        total_sales = kw_summary['销售额'].sum()
        avg_roas = (total_sales / total_spent * 100) if total_spent > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("全账号总支出 (含税)", f"₩{total_spent:,.0f}")
        m2.metric("全账号总销售额", f"₩{total_sales:,.0f}")
        m3.metric("全账号平均 ROAS", f"{avg_roas:.2f}%")

        # --- 6. 核心看板展示 (向下做满) ---
        tab1, tab2 = st.tabs(["🎯 对比看板", "📄 明细明细表"])

        with tab1:
            st.write("### 搜索 vs 非搜索 对比 (按产品)")
            def highlight_total_row(row):
                if row['维度分类'] == '📌 产品总计':
                    return ['background-color: #e8f4ea; font-weight: bold; border-bottom: 2px solid #28a745'] * len(row)
                return [''] * len(row)

            # 设置 height 为 800，让看板向下做满
            st.dataframe(
                final_compare.style.apply(highlight_total_row, axis=1),
                column_config={
                    "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                    "真实支出": st.column_config.NumberColumn(format="₩%d"),
                    "销售额": st.column_config.NumberColumn(format="₩%d"),
                    "目标指标": st.column_config.NumberColumn(format="%d%%")
                },
                hide_index=True, use_container_width=True, height=800
            )

        with tab2:
            st.write("### 关键词全维度明细")
            unique_p = kw_summary['产品编号'].unique()
            p_color_map = {p: '#f9f9f9' if i % 2 == 0 else '#ffffff' for i, p in enumerate(unique_p)}
            def zebra_style(row):
                return [f'background-color: {p_color_map[row["产品编号"]]}'] * len(row)

            # 同样设置长屏显示
            st.dataframe(
                kw_summary.drop(columns=['维度分类']).style.apply(zebra_style, axis=1),
                column_config={
                    "支出占比": st.column_config.NumberColumn(format="%.1f%%"),
                    "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                    "真实支出": st.column_config.NumberColumn(format="₩%d"),
                    "目标指标": st.column_config.NumberColumn(format="%d%%")
                },
                hide_index=True, use_container_width=True, height=800
            )

        # 侧边栏下载
        csv = kw_summary.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.divider()
        st.sidebar.download_button("📥 下载分析报告 (CSV)", csv, "LxU_Full_Analysis.csv", "text/csv")
else:
    st.info("👋 请批量上传广告报表。建议文件名包含店铺名，方便多店铺管理。")
