import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告数据汇总工具", layout="wide")

st.title("📊 广告数据自动化汇总与分析")

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

        # 1. 属性提取函数 (产品编号, 目标指标, 策略日期)
        def extract_info(row):
            camp_name = str(row.iloc[5]) if len(row) > 5 else ""
            grp_name = str(row.iloc[6]) if len(row) > 6 else ""
            full_text = f"{camp_name} {grp_name}"
            
            p_code = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code.group(0).upper() if p_code else "未识别"
            
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = target_match.group(1) if target_match else "0"
            
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "未知"
            
            return pd.Series([p_code, target_val, mod_date])

        # 应用提取
        raw_df[['产品编号', '目标指标', '策略日期']] = raw_df.apply(extract_info, axis=1)

        # 2. 定义汇总需要的列索引
        # A日期(0), M关键词(12), N展示(13), O点击(14), P广告费(15), Q点击率(16), AD总销量(29)
        # 注意：Python索引从0开始，所以 A=0, M=12, N=13, O=14, P=15, Q=16, AD=29
        
        # 提取核心计算列并重命名，防止索引混乱
        analysis_df = raw_df.copy()
        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[0]: '日期',
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '展示次数',
            analysis_df.columns[14]: '点击次数',
            analysis_df.columns[15]: '原始广告费',
            analysis_df.columns[29]: '总销量'
        })

        # 3. 执行聚合计算
        # 按 产品编号、日期、关键词 汇总
        summary_df = analysis_df.groupby(['产品编号', '日期', '关键词', '目标指标', '策略日期']).agg({
            '展示次数': 'sum',
            '点击次数': 'sum',
            '原始广告费': 'sum',
            '总销量': 'sum'
        }).reset_index()

        # 4. 计算真实指标
        # 广告费含税 (乘以 1.1)
        summary_df['真实广告费(含税)'] = summary_df['原始广告费'] * 1.1
        
        # 重新计算点击率 (点击 / 展示)
        summary_df['真实点击率(%)'] = (summary_df['点击次数'] / summary_df['展示次数'] * 100).round(2)
        
        # 计算真实 ROAS (总销量 / 真实广告费)
        summary_df['真实ROAS(%)'] = (summary_df['总销量'] / summary_df['真实广告费(含税)'] * 100).round(2)
        
        # 计算真实 CPC (真实广告费 / 点击数)
        summary_df['真实CPC'] = (summary_df['真实广告费(含税)'] / summary_df['点击次数']).round(2)

        # 清洗无穷大值（防止点击数为0导致错误）
        summary_df = summary_df.replace([float('inf'), -float('inf')], 0).fillna(0)

        # --- 界面展示 ---
        st.success(f"✅ 汇总完成！已对 {len(summary_df)} 组数据进行了含税成本核算。")

        # 数据预览
        st.subheader("汇总分析报表")
        st.dataframe(summary_df)

        # 导出汇总表
        final_csv = summary_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载含税汇总分析表", final_csv, "LxU_Financial_Report.csv", "text/csv")

        # 简单的看板：查看各产品总表现
        st.divider()
        st.subheader("产品维度总计 (含税)")
        product_sum = summary_df.groupby('产品编号').agg({
            '真实广告费(含税)': 'sum',
            '总销量': 'sum'
        })
        product_sum['总ROAS(%)'] = (product_sum['总销量'] / product_sum['真实广告费(含税)'] * 100).round(2)
        st.bar_chart(product_sum['总ROAS(%)'])

else:
    st.info("请批量上传每日广告报表开始汇总。")
