import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告智能决策看板", layout="wide")

st.title("🚀 LxU 广告全维度明细看板")
st.markdown("已调整排序：**非搜索区域汇总**置于首行，**手动词**居中，**产品总计**置底。")

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

        # 3. 清洗与归一化
        analysis_df = raw_df.copy()
        mask_ns = (analysis_df.iloc[:, 12].isna()) | \
                  (analysis_df.iloc[:, 11].str.contains('비검색|非搜索', na=False)) | \
                  (analysis_df.iloc[:, 12].astype(str) == 'nan')
        
        analysis_df.iloc[:, 12] = analysis_df.iloc[:, 12].astype(str).str.strip().replace({'nan': '🤖 非搜索区域', '': '🤖 非搜索区域'})
        analysis_df.iloc[:, 11] = analysis_df.iloc[:, 11].astype(str).str.strip()
        
        analysis_df.loc[mask_ns, analysis_df.columns[12]] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, analysis_df.columns[11]] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '策略日期'] = '汇总'

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面', analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '展示', analysis_df.columns[14]: '点击',
            analysis_df.columns[15]: '原支出', analysis_df.columns[29]: '销量', analysis_df.columns[32]: '销售额'
        })

        # 4. 聚合计算
        # a. 关键词级明细
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

        # c. 【核心修正】设置排序权重
        # 权重：非搜索=0, 手动词=1, 总计=2
        kw_summary['sort_weight'] = kw_summary['关键词'].apply(lambda x: 0 if '非搜索' in x else 1)
        product_sum['sort_weight'] = 2

        combined_df = pd.concat([kw_summary, product_sum], ignore_index=True)
        # 排序优先级：产品编号 -> 权重 -> 支出(降序)
        combined_df = combined_df.sort_values(['产品编号', 'sort_weight', '原支出'], ascending=[True, True, False])

        # 5. 指标计算
        combined_df['真实支出'] = (combined_df['原支出'] * 1.1).round(0)
        combined_df['真实ROAS'] = (combined_df['销售额'] / combined_df['真实支出'] * 100).round(2)
        
        p_total_spend_map = product_sum.set_index('产品编号')['原支出'] * 1.1
        combined_df['支出占比'] = combined_df.apply(
            lambda x: (x['真实支出'] / p_total_spend_map[x['产品编号']] * 100) if x['sort_weight'] != 2 else 100.0, axis=1
        ).round(1)

        combined_df = combined_df.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 6. 界面渲染
        unique_p = combined_df['产品编号'].unique()
        p_color_map = {p: '#f9f9f9' if i % 2 == 0 else '#ffffff' for i, p in enumerate(unique_p)}

        def apply_row_styles(row):
            base_color = p_color_map[row['产品编号']]
            # 总计行样式
            if row['sort_weight'] == 2:
                return ['background-color: #e8f4ea; font-weight: bold; border-top: 2px solid #ccc'] * len(row)
            # 非搜索行样式（可选：浅蓝色区分）
            if row['sort_weight'] == 0:
                return [f'background-color: {base_color}; color: #0056b3; font-weight: 500'] * len(row)
            return [f'background-color: {base_color}'] * len(row)

        st.dataframe(
            combined_df.style.apply(apply_row_styles, axis=1),
            column_config={
                "sort_weight": None, # 隐藏排序辅助列
                "支出占比": st.column_config.NumberColumn(format="%.1f%%"),
                "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                "目标指标": st.column_config.NumberColumn(format="%d%%"),
                "真实支出": st.column_config.NumberColumn(format="₩%d"),
                "销售额": st.column_config.NumberColumn(format="₩%d")
            },
            hide_index=True,
            use_container_width=True,
            height=1000 # 再次拉长预览窗口
        )

        # 7. 下载
        csv_data = combined_df.drop(columns=['sort_weight']).to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("📥 下载完整报告", csv_data, "LxU_Integrated_Report.csv", "text/csv")

else:
    st.info("👋 请批量上传报表。")
