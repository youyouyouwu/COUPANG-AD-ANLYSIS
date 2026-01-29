import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告全量分析看板", layout="wide")

st.title("📊 LxU 广告关键词明细（含产品总计）")
st.markdown("已实现：每个产品的关键词下方自动紧跟该产品的**汇总数据行**。")

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

        # 1. 属性提取
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

        # 2. 清洗与归一化
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

        # 3. 聚合关键词明细
        kw_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index()

        # 4. 【关键步骤】计算产品总计并插入明细
        product_sum = kw_summary.groupby('产品编号').agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        product_sum['展示版面'] = '📌 总计'
        product_sum['关键词'] = '📌 产品总计'
        product_sum['策略日期'] = 'TOTAL'

        # 合并明细与总计，并排序确保总计在每个产品最下方
        # 我们给总计行一个排序权重，让它排在最后
        kw_summary['is_total'] = 0
        product_sum['is_total'] = 1
        combined_final = pd.concat([kw_summary, product_sum], ignore_index=True)
        combined_final = combined_final.sort_values(['产品编号', 'is_total', '原支出'], ascending=[True, True, False])

        # 5. 指标计算
        combined_final['真实支出'] = (combined_final['原支出'] * 1.1).round(0)
        combined_final['真实ROAS'] = (combined_final['销售额'] / combined_final['真实支出'] * 100).round(2)
        
        # 支出占比：明细行相对于产品总额的比例
        p_total_spend = product_sum.set_index('产品编号')['原支出'] * 1.1
        combined_final['支出占比'] = combined_final.apply(
            lambda x: (x['真实支出'] / p_total_spend[x['产品编号']] * 100) if x['is_total'] == 0 else 100.0, axis=1
        ).round(1)

        combined_final = combined_final.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 6. 界面渲染（斑马纹 + 总计高亮）
        st.subheader("关键词全维度明细（含产品总计行）")
        
        unique_p = combined_final['产品编号'].unique()
        p_color_map = {p: '#f9f9f9' if i % 2 == 0 else '#ffffff' for i, p in enumerate(unique_p)}

        def integrated_style(row):
            # 基础斑马纹：按产品编号变色
            base_color = p_color_map[row['产品编号']]
            # 如果是总计行，强制变色并加粗
            if row['is_total'] == 1:
                return ['background-color: #e8f4ea; font-weight: bold; border-top: 1px solid #ccc'] * len(row)
            return [f'background-color: {base_color}'] * len(row)

        st.dataframe(
            combined_final.drop(columns=['is_total']).style.apply(integrated_style, axis=1),
            column_config={
                "支出占比": st.column_config.NumberColumn(format="%.1f%%"),
                "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                "真实支出": st.column_config.NumberColumn(format="₩%d"),
                "销售额": st.column_config.NumberColumn(format="₩%d"),
                "目标指标": st.column_config.NumberColumn(format="%d%%")
            },
            hide_index=True, use_container_width=True
        )

        # 下载
        csv = combined_final.drop(columns=['is_total']).to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("📥 下载完整汇总报告", csv, "LxU_Integrated_Ads.csv", "text/csv")
else:
    st.info("👋 请批量上传报表。")
