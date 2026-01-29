import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告全维度分析", layout="wide")

# --- 样式定义：斑马纹与高亮 ---
def style_dataframe(df):
    # 创建一个产品编号到索引的映射，用于判断奇偶
    unique_p_codes = df['产品编号'].unique()
    p_code_map = {code: i for i, code in enumerate(unique_p_codes)}
    
    def zebra_by_product(row):
        # 根据产品编号的顺序切换颜色
        is_even = p_code_map[row['产品编号']] % 2 == 0
        bg_color = '#f9f9f9' if is_even else '#ffffff' # 浅灰与白色交替
        return [f'background-color: {bg_color}'] * len(row)

    # 应用样式
    styled = df.style.apply(zebra_by_product, axis=1)
    
    # 针对 ROAS 达标情况做文字高亮
    def highlight_roas(val, target):
        if target > 0 and val < target:
            return 'color: #d73a49; font-weight: bold;' # 不达标显红
        elif target > 0 and val >= target:
            return 'color: #28a745; font-weight: bold;' # 达标显绿
        return ''

    return styled

st.title("📊 LxU 广告数据全维度看板")

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
        
        analysis_df['展示版面'] = analysis_df.iloc[:, 11].astype(str).str.strip()
        analysis_df['关键词'] = analysis_df.iloc[:, 12].astype(str).str.strip()
        
        analysis_df.loc[mask_ns, '展示版面'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '关键词'] = '🤖 非搜索区域'

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[13]: '展示', analysis_df.columns[14]: '点击',
            analysis_df.columns[15]: '原支出', analysis_df.columns[32]: '销售额'
        })

        # 3. 聚合计算
        kw_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标']).agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销售额': 'sum'
        }).reset_index().sort_values('产品编号') # 必须按产品编号排序，斑马纹才有效

        kw_summary['真实支出'] = (kw_summary['原支出'] * 1.1).round(0)
        kw_summary['真实ROAS'] = (kw_summary['销售额'] / kw_summary['真实支出'] * 100).round(2)
        kw_summary['支出占比'] = (kw_summary['真实支出'] / kw_summary.groupby('产品编号')['真实支出'].transform('sum') * 100).round(1)
        kw_summary = kw_summary.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 4. 对比看板计算
        kw_summary['维度'] = kw_summary['关键词'].apply(lambda x: '🤖 非搜索区域' if '非搜索' in x else '🔎 搜索区域')
        area_summary = kw_summary.groupby(['产品编号', '维度']).agg({
            '展示': 'sum', '点击': 'sum', '真实支出': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index().sort_values('产品编号')
        area_summary['真实ROAS'] = (area_summary['销售额'] / area_summary['真实支出'] * 100).round(2)
        area_summary['支出占比'] = (area_summary['真实支出'] / area_summary.groupby('产品编号')['真实支出'].transform('sum') * 100).round(1)

        # --- 界面展示 ---
        tab1, tab2 = st.tabs(["🎯 产品对比看板 (斑马纹)", "📄 关键词明细表"])

        with tab1:
            # 使用 styled 展示斑马纹
            st.write("### 搜索 vs 非搜索对比")
            st.table(area_summary.assign(
                真实ROAS=area_summary['真实ROAS'].map('{:.2f}%'.format),
                支出占比=area_summary['支出占比'].map('{:.1f}%'.format),
                销售额=area_summary['销售额'].map('₩{:,.0f}'.format),
                真实支出=area_summary['真实支出'].map('₩{:,.0f}'.format)
            )) 
            # 注意：st.table 默认支持斑马纹，且适合展示这类汇总数据

        with tab2:
            st.write("### 关键词明细")
            # 针对明细，我们使用 dataframe 并应用自定义斑马纹
            st.dataframe(
                kw_summary.drop(columns=['维度']),
                column_config={
                    "支出占比": st.column_config.NumberColumn(format="%.1f%%"),
                    "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                    "真实支出": st.column_config.NumberColumn(format="₩%d"),
                    "目标指标": st.column_config.NumberColumn(format="%d%%")
                },
                hide_index=True, use_container_width=True
            )

        csv = kw_summary.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("📥 下载完整分析报告", csv, "LxU_Full_Analysis.csv", "text/csv")
else:
    st.info("👋 请上传广告报表。")
