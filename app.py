import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告全维度汇总分析", layout="wide")

st.title("📊 LxU 广告关键词与版面全周期汇总")
st.markdown("已集成：**非搜索区域强制合并**、**1.1倍含税核算**、**支出占比分析**。")

# 1. 文件上传
uploaded_files = st.file_uploader("批量上传广告报表 (CSV/Excel)", type=['csv', 'xlsx'], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            # 兼容韩文编码
            df = pd.read_csv(file, encoding='cp949') if file.name.endswith('.csv') else pd.read_excel(file)
            all_data.append(df)
        except:
            df = pd.read_csv(file, encoding='utf-8-sig')
            all_data.append(df)

    if all_data:
        raw_df = pd.concat(all_data, ignore_index=True)

        # --- 数据提取函数 ---
        def extract_info(row):
            # F列(5)和G列(6)
            camp_name = str(row.iloc[5]) if len(row) > 5 else ""
            grp_name = str(row.iloc[6]) if len(row) > 6 else ""
            full_text = f"{camp_name} {grp_name}"
            
            p_code = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code.group(0).upper() if p_code else "未识别"
            
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = int(target_match.group(1)) if target_match else 0
            
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "未知"
            
            return pd.Series([p_code, target_val, mod_date])

        # 应用提取属性
        raw_df[['产品编号', '目标指标', '策略日期']] = raw_df.apply(extract_info, axis=1)

        # --- 数据清洗与强制合并非搜索区域 ---
        analysis_df = raw_df.copy()

        # 强制处理 M列(索引12) 为字符串并清洗
        analysis_df.iloc[:, 12] = analysis_df.iloc[:, 12].astype(str).str.strip().replace({'nan': '非搜索区域', '': '非搜索区域'})
        
        # 处理 L列(索引11)
        analysis_df.iloc[:, 11] = analysis_df.iloc[:, 11].astype(str).str.strip()

        # 关键：如果关键词包含“非搜索”或为空，则展示版面也统一，确保 groupby 合并
        mask = (analysis_df.iloc[:, 12] == '非搜索区域') | (analysis_df.iloc[:, 11].str.contains('비검색|非搜索', na=False))
        analysis_df.loc[mask, analysis_df.columns[12]] = '非搜索区域'
        analysis_df.loc[mask, analysis_df.columns[11]] = '非搜索区域'

        # 重命名列
        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面',
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '总展示',
            analysis_df.columns[14]: '总点击',
            analysis_df.columns[15]: '原始广告费',
            analysis_df.columns[29]: '总销量(单数)',
            analysis_df.columns[32]: '总转化销售额'
        })

        # --- 执行聚合 ---
        summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '总展示': 'sum',
            '总点击': 'sum',
            '原始广告费': 'sum',
            '总销量(单数)': 'sum',
            '总转化销售额': 'sum'
        }).reset_index()

        # --- 指标计算 ---
        summary['真实广告费(含税)'] = (summary['原始广告费'] * 1.1).round(0)
        
        # 计算产品总支出用于占比
        total_spend_per_p = summary.groupby('产品编号')['真实广告费(含税)'].transform('sum')
        summary['支出占比'] = (summary['真实广告费(含税)'] / total_spend_per_p * 100).round(2)

        summary['真实ROAS'] = (summary['总转化销售额'] / summary['真实广告费(含税)'] * 100).round(2)
        summary['真实点击率'] = (summary['总点击'] / summary['总展示'] * 100).round(2)
        summary['真实CPC'] = (summary['真实广告费(含税)'] / summary['总点击']).round(0)

        # 清洗异常值
        summary = summary.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 盈亏判定
        summary['盈亏状态'] = summary.apply(lambda r: "✅ 达标" if r['目标指标'] > 0 and r['真实ROAS'] >= r['目标指标'] else ("未设目标" if r['目标指标']==0 else "❌ 亏损"), axis=1)

        # --- 结果展示 ---
        st.success("✅ 数据分析完成！")

        # 快速筛选
        st.sidebar.header("数据筛选")
        p_list = st.sidebar.multiselect("筛选产品", options=summary['产品编号'].unique())
        if p_list:
            summary = summary[summary['产品编号'].isin(p_list)]

        st.dataframe(
            summary,
            column_config={
                "支出占比": st.column_config.NumberColumn("支出占比", format="%.2f%%"),
                "目标指标": st.column_config.NumberColumn("目标指标", format="%d%%"),
                "真实ROAS": st.column_config.NumberColumn("真实ROAS", format="%.2f%%"),
                "真实点击率": st.column_config.NumberColumn("真实点击率", format="%.2f%%"),
                "总转化销售额": st.column_config.NumberColumn("销售额", format="₩%d"),
                "真实广告费(含税)": st.column_config.NumberColumn("真实广告费", format="₩%d"),
                "真实CPC": st.column_config.NumberColumn("CPC", format="₩%d")
            },
            hide_index=True,
            use_container_width=True
        )

        # 导出
        csv = summary.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载汇总报表", csv, "LxU_Ad_Summary.csv", "text/csv")
else:
    st.info("👋 请批量上传从 Coupang 导出的原始广告报表。")
