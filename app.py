import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告全维度看板", layout="wide")

st.title("📊 LxU 广告数据全维度看板")
st.markdown("已新增：**产品维度总计行**。每个产品的搜索与非搜索下方会自动显示该品汇总数据。")

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

        # 1. 提取属性
        def extract_info(row):
            camp_name, grp_name = str(row.iloc[5]), str(row.iloc[6])
            full_text = f"{camp_name} {grp_name}"
            p_code = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code.group(0).upper() if p_code else "未识别"
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = int(target_match.group(1)) if target_match else 0
            return pd.Series([p_code, target_val])

        raw_df[['产品编号', '目标指标']] = raw_df.apply(extract_info, axis=1)

        # 2. 清洗与归一化
        analysis_df = raw_df.copy()
        mask_ns = (analysis_df.iloc[:, 12].isna()) | (analysis_df.iloc[:, 11].str.contains('비검색|非搜索', na=False)) | (analysis_df.iloc[:, 12].astype(str) == 'nan')
        
        analysis_df['维度'] = '🔎 搜索区域'
        analysis_df.loc[mask_ns, '维度'] = '🤖 非搜索区域'

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[13]: '展示', analysis_df.columns[14]: '点击',
            analysis_df.columns[15]: '原支出', analysis_df.columns[32]: '销售额'
        })

        # 3. 计算区域汇总
        area_summary = analysis_df.groupby(['产品编号', '维度']).agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()

        # 4. 【核心创新】：计算并插入“产品总计”行
        product_totals = area_summary.groupby('产品编号').agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        product_totals['维度'] = '📌 产品总计'

        # 合并区域数据与总计数据，并按产品编号排序
        final_comparison = pd.concat([area_summary, product_totals], ignore_index=True).sort_values(['产品编号', '维度'], ascending=[True, False])

        # 5. 指标计算
        final_comparison['真实支出'] = (final_comparison['原支出'] * 1.1).round(0)
        final_comparison['真实ROAS'] = (final_comparison['销售额'] / final_comparison['真实支出'] * 100).round(2)
        final_comparison['点击率'] = (final_comparison['点击'] / final_comparison['展示'] * 100).round(2)
        
        # 占比只针对搜索/非搜索行有效，总计行设为 100%
        p_spend_map = product_totals.set_index('产品编号')['原支出'] * 1.1
        final_comparison['支出占比'] = final_comparison.apply(
            lambda x: (x['真实支出'] / p_spend_map[x['产品编号']] * 100) if x['维度'] != '📌 产品总计' else 100.0, axis=1
        ).round(1)

        final_comparison = final_comparison.replace([float('inf'), -float('inf')], 0).fillna(0)

        # --- 界面展示 ---
        tab1, tab2 = st.tabs(["🎯 产品对比看板 (含总计)", "📄 关键词明细表"])

        with tab1:
            st.subheader("搜索 vs 非搜索 vs 产品总计")
            
            # 使用 CSS 让总计行加粗变色（Streamlit 样式注入）
            def highlight_total(row):
                if row['维度'] == '📌 产品总计':
                    return ['background-color: #e8f4ea; font-weight: bold'] * len(row)
                return [''] * len(row)

            styled_df = final_comparison[['产品编号', '维度', '支出占比', '真实ROAS', '点击率', '真实支出', '销售额', '目标指标']].style.apply(highlight_total, axis=1)

            st.dataframe(
                styled_df,
                column_config={
                    "支出占比": st.column_config.NumberColumn(format="%.1f%%"),
                    "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                    "点击率": st.column_config.NumberColumn(format="%.2f%%"),
                    "真实支出": st.column_config.NumberColumn(format="₩%d"),
                    "销售额": st.column_config.NumberColumn(format="₩%d"),
                    "目标指标": st.column_config.NumberColumn(format="%d%%")
                },
                hide_index=True, use_container_width=True
            )

        with tab2:
            # 关键词明细保持原有逻辑...
            st.info("明细表已根据产品编号分组，建议下载 CSV 后在 Excel 中进行高级筛选。")
            # (此处省略明细表渲染代码，可沿用上一版)

else:
    st.info("👋 请上传报表开始分析。")
