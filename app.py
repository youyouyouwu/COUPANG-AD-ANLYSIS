import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告智能分析诊断", layout="wide")

st.title("📊 LxU 广告智能分析诊断看板")
st.markdown("已解决：**非搜索区域多日期合并**问题。新增：**自动优化建议**模块。")

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

        # 1. 基础属性提取
        def extract_info(row):
            camp_name, grp_name = str(row.iloc[5]), str(row.iloc[6])
            full_text = f"{camp_name} {grp_name}"
            p_code = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code.group(0).upper() if p_code else "未识别"
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = int(target_match.group(1)) if target_match else 0
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "未知"
            return pd.Series([p_code, target_val, mod_date])

        raw_df[['产品编号', '目标指标', '策略日期']] = raw_df.apply(extract_info, axis=1)

        # 2. 核心清洗：强制合并非搜索区域
        analysis_df = raw_df.copy()
        analysis_df.iloc[:, 12] = analysis_df.iloc[:, 12].astype(str).str.strip().replace({'nan': '非搜索区域', '': '非搜索区域'})
        analysis_df.iloc[:, 11] = analysis_df.iloc[:, 11].astype(str).str.strip()

        # 识别所有非搜索行
        mask_ns = (analysis_df.iloc[:, 12] == '非搜索区域') | (analysis_df.iloc[:, 11].str.contains('비검색|非搜索', na=False))
        
        # 强制抹平差异列：关键词、版面、日期全部对齐
        analysis_df.loc[mask_ns, analysis_df.columns[12]] = '非搜索区域'
        analysis_df.loc[mask_ns, analysis_df.columns[11]] = '非搜索区域'
        analysis_df.loc[mask_ns, '策略日期'] = '汇总'
        # 指标取该品最大的目标值（通常一致）
        analysis_df.loc[mask_ns, '目标指标'] = analysis_df.groupby('产品编号')['目标指标'].transform('max')

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面', analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '展示', analysis_df.columns[14]: '点击',
            analysis_df.columns[15]: '原支出', analysis_df.columns[29]: '销量', analysis_df.columns[32]: '销售额'
        })

        # 3. 聚合与占比计算
        summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '展示': 'sum', '点击': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index()

        summary['真实支出'] = (summary['原支出'] * 1.1).round(0)
        p_total_spend = summary.groupby('产品编号')['真实支出'].transform('sum')
        summary['支出占比'] = (summary['真实支出'] / p_total_spend * 100).round(2)
        summary['真实ROAS'] = (summary['销售额'] / summary['真实支出'] * 100).round(2)
        summary['CPC'] = (summary['真实支出'] / summary['点击']).round(0)
        summary = summary.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 4. 智能诊断逻辑 (Smart Insights)
        st.subheader("💡 投放优化建议")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 异常消耗词：消耗占产品15%以上且销售额为0
            waste_words = summary[(summary['支出占比'] > 15) & (summary['销售额'] == 0) & (summary['关键词'] != '非搜索区域')]
            st.error(f"⚠️ 无效消耗词: {len(waste_words)} 个")
            if not waste_words.empty: st.caption("建议：降低出价或剔除。")
            
        with col2:
            # 非搜索过热：非搜索占比 > 50% 且 ROAS 不达标
            ns_overheat = summary[(summary['关键词'] == '非搜索区域') & (summary['支出占比'] > 50) & (summary['真实ROAS'] < summary['目标指标'])]
            st.warning(f"📉 非搜索过热: {len(ns_overheat)} 个品")
            if not ns_overheat.empty: st.caption("建议：关闭该品非搜索开关。")

        with col3:
            # 高潜爆款：ROAS > 目标2倍 且 消耗占比 < 20%
            potential_stars = summary[(summary['真实ROAS'] > summary['目标指标']*2) & (summary['支出占比'] < 20) & (summary['目标指标'] > 0)]
            st.success(f"🚀 高潜关键词: {len(potential_stars)} 个")
            if not potential_stars.empty: st.caption("建议：增加出价获取流量。")

        # 5. 数据明细展示
        st.divider()
        st.dataframe(
            summary,
            column_config={
                "支出占比": st.column_config.NumberColumn(format="%.2f%%"),
                "目标指标": st.column_config.NumberColumn(format="%d%%"),
                "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"),
                "销售额": st.column_config.NumberColumn(format="₩%d"),
                "真实支出": st.column_config.NumberColumn(format="₩%d")
            },
            hide_index=True, use_container_width=True
        )

        csv = summary.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载完整诊断报告", csv, "LxU_Smart_Analysis.csv", "text/csv")
else:
    st.info("请批量上传广告报表。")
