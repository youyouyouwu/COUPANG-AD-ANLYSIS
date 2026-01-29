import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告区域对比分析", layout="wide")

st.title("📊 产品搜索 vs 非搜索对比分析")
st.markdown("该页面将每个产品的**手动搜索词总和**与**系统非搜索区域**进行并列对比。")

uploaded_files = st.file_uploader("批量上传报表", type=['csv', 'xlsx'], accept_multiple_files=True)

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

        # 2. 清洗逻辑
        analysis_df = raw_df.copy()
        # 统一识别非搜索
        mask_ns = (analysis_df.iloc[:, 12].isna()) | (analysis_df.iloc[:, 11].str.contains('비검색|非搜索', na=False))
        
        # 核心分类：将所有流量归为“搜索区域”或“非搜索区域”
        analysis_df['对比维度'] = '🔎 搜索区域(手动)'
        analysis_df.loc[mask_ns, '对比维度'] = '🤖 非搜索区域(自动)'
        
        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[13]: '展示', analysis_df.columns[14]: '点击',
            analysis_df.columns[15]: '原支出', analysis_df.columns[32]: '销售额'
        })

        # 3. 产品维度对比聚合
        area_comparison = analysis_df.groupby(['产品编号', '对比维度']).agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()

        # 计算对比指标
        area_comparison['真实支出'] = (area_comparison['原支出'] * 1.1).round(0)
        area_comparison['真实ROAS'] = (area_comparison['销售额'] / area_comparison['真实支出'] * 100).round(2)
        area_comparison['点击率'] = (area_comparison['点击'] / area_comparison['展示'] * 100).round(2)
        
        # 计算该产品内部的支出占比
        area_comparison['支出占比'] = (area_comparison['真实支出'] / area_comparison.groupby('产品编号')['真实支出'].transform('sum') * 100).round(1)

        # 4. 界面展示
        st.subheader("🎯 产品级：搜索 vs 非搜索 对比看板")
        
        # 侧边栏筛选特定产品查看
        p_list = st.sidebar.multiselect("选择要对比的产品", options=area_comparison['产品编号'].unique())
        display_compare = area_comparison[area_comparison['产品编号'].isin(p_list)] if p_list else area_comparison

        st.dataframe(
            display_compare,
            column_config={
                "支出占比": st.column_config.NumberColumn("支出占比", format="%.1f%%"),
                "真实ROAS": st.column_config.NumberColumn("真实ROAS", format="%.2f%%"),
                "点击率": st.column_config.NumberColumn("点击率", format="%.2f%%"),
                "真实支出": st.column_config.NumberColumn("真实支出", format="₩%d"),
                "销售额": st.column_config.NumberColumn("销售额", format="₩%d"),
                "目标指标": st.column_config.NumberColumn("目标指标", format="%d%%")
            },
            hide_index=True, use_container_width=True
        )

        # 可视化对比
        if p_list and len(p_list) == 1:
            st.info(f"正在分析产品 {p_list[0]} 的流量构成")
            st.bar_chart(display_compare.set_index('对比维度')['支出占比'])

        st.divider()
        st.subheader("📄 关键词明细（包含汇总后的非搜索行）")
        st.caption("注：此表显示具体的关键词表现，非搜索区域已自动合并为一行。")
        # 此处可以放置之前的明细 summary 表代码...
