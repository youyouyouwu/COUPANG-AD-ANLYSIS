import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告全维度分析", layout="wide")

st.title("📊 LxU 广告数据全维度看板")
st.markdown("已集成：**对比看板**、**关键词明细**、**智能诊断**。")

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

        # 1. 提取核心属性
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

        # 2. 数据清洗与对齐
        analysis_df = raw_df.copy()
        # 统一非搜索标记
        mask_ns = (analysis_df.iloc[:, 12].isna()) | (analysis_df.iloc[:, 11].str.contains('비검색|非搜索', na=False)) | (analysis_df.iloc[:, 12].astype(str) == 'nan')
        
        analysis_df['展示版面'] = analysis_df.iloc[:, 11].astype(str).str.strip()
        analysis_df['关键词'] = analysis_df.iloc[:, 12].astype(str).str.strip()
        
        # 强制归一化非搜索项
        analysis_df.loc[mask_ns, '展示版面'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '关键词'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '策略日期'] = '汇总'

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[13]: '展示', analysis_df.columns[14]: '点击',
            analysis_df.columns[15]: '原支出', analysis_df.columns[29]: '销量', analysis_df.columns[32]: '销售额'
        })

        # 3. 聚合计算 (关键词级)
        kw_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index()

        kw_summary['真实支出'] = (kw_summary['原支出'] * 1.1).round(0)
        kw_summary['真实ROAS'] = (kw_summary['销售额'] / kw_summary['真实支出'] * 100).round(2)
        kw_summary['支出占比'] = (kw_summary['真实支出'] / kw_summary.groupby('产品编号')['真实支出'].transform('sum') * 100).round(1)
        kw_summary = kw_summary.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 4. 聚合计算 (产品对比级)
        # 将流量简单分为两类
        kw_summary['对比维度'] = kw_summary['关键词'].apply(lambda x: '🤖 非搜索区域' if '非搜索' in x else '🔎 搜索区域(手动)')
        area_summary = kw_summary.groupby(['产品编号', '对比维度']).agg({
            '展示': 'sum', '点击': 'sum', '真实支出': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        area_summary['真实ROAS'] = (area_summary['销售额'] / area_summary['真实支出'] * 100).round(2)
        area_summary['支出占比'] = (area_summary['真实支出'] / area_summary.groupby('产品编号')['真实支出'].transform('sum') * 100).round(1)

        # --- 界面展示 (Tabs 布局) ---
        tab1, tab2 = st.tabs(["🎯 产品级对比看板", "📄 关键词明细表"])

        with tab1:
            st.subheader("搜索 vs 非搜索 流量构成对比")
            st.dataframe(
                area_summary,
                column_config={
                    "支出占比": st.column_config.NumberColumn(format="%.1f%%"),
                    "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                    "真实支出": st.column_config.NumberColumn(format="₩%d"),
                    "销售额": st.column_config.NumberColumn(format="₩%d"),
                    "目标指标": st.column_config.NumberColumn(format="%d%%")
                },
                hide_index=True, use_container_width=True
            )

        with tab2:
            st.subheader("全周期关键词表现明细")
            st.dataframe(
                kw_summary.drop(columns=['对比维度']),
                column_config={
                    "支出占比": st.column_config.NumberColumn(format="%.1f%%"),
                    "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                    "真实支出": st.column_config.NumberColumn(format="₩%d"),
                    "目标指标": st.column_config.NumberColumn(format="%d%%")
                },
                hide_index=True, use_container_width=True
            )

        # 导出汇总数据
        csv = kw_summary.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("📥 下载完整分析报告", csv, "LxU_Full_Analysis.csv", "text/csv")
else:
    st.info("👋 请上传广告报表开始分析。")
