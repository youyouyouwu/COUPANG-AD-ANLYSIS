import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 关键词全周期分析", layout="wide")

st.title("📈 关键词全周期表现汇总")
st.markdown("该页面将合并所有日期数据，展示每个产品下各关键词的**整体产出比**。")

uploaded_files = st.file_uploader("批量上传报表", type=['csv', 'xlsx'], accept_multiple_files=True)

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

        # 1. 提取属性 (产品编号, 目标指标, 策略日期)
        def extract_info(row):
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

        raw_df[['产品编号', '目标指标', '策略日期']] = raw_df.apply(extract_info, axis=1)

        # 2. 列名重命名 (根据索引 A, M, N, O, P, AD)
        analysis_df = raw_df.copy()
        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '总展示',
            analysis_df.columns[14]: '总点击',
            analysis_df.columns[15]: '原始广告费',
            analysis_df.columns[29]: '总销量'
        })

        # 3. 执行全周期聚合 (去掉了日期维度)
        # 按 产品编号、关键词、目标指标 进行汇总
        keyword_summary = analysis_df.groupby(['产品编号', '关键词', '目标指标', '策略日期']).agg({
            '总展示': 'sum',
            '总点击': 'sum',
            '原始广告费': 'sum',
            '总销量': 'sum'
        }).reset_index()

        # 4. 指标二次计算
        keyword_summary['真实广告费(含税)'] = (keyword_summary['原始广告费'] * 1.1).round(0)
        keyword_summary['真实ROAS(%)'] = (keyword_summary['总销量'] / keyword_summary['真实广告费(含税)'] * 100).round(2)
        keyword_summary['真实点击率(%)'] = (keyword_summary['总点击'] / keyword_summary['总展示'] * 100).round(2)
        keyword_summary['真实CPC'] = (keyword_summary['真实广告费(含税)'] / keyword_summary['总点击']).round(0)

        # 清洗异常值
        keyword_summary = keyword_summary.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 5. 盈亏状态判定
        def check_status(row):
            if row['目标指标'] == 0: return "未设目标"
            return "✅ 达标" if row['真实ROAS(%)'] >= row['目标指标'] else "❌ 亏损"
        
        keyword_summary['盈亏状态'] = keyword_summary.apply(check_status, axis=1)

        # --- 界面展示 ---
        st.success(f"✅ 汇总完成！已分析 {len(keyword_summary)} 个独立关键词的长期表现。")

        # 侧边栏：快速筛选
        st.sidebar.header("数据筛选")
        selected_p = st.sidebar.multiselect("选择产品编号", options=keyword_summary['产品编号'].unique())
        if selected_p:
            keyword_summary = keyword_summary[keyword_summary['产品编号'].isin(selected_p)]

        status_filter = st.sidebar.multiselect("盈亏状态", options=["✅ 达标", "❌ 亏损", "未设目标"])
        if status_filter:
            keyword_summary = keyword_summary[keyword_summary['盈亏状态'].isin(status_filter)]

        # 数据表格美化：使用颜色标记
        st.subheader("关键词全周期表现明细")
        
        # 定义高亮函数
        def highlight_status(val):
            color = 'red' if val == "❌ 亏损" else ('green' if val == "✅ 达标" else 'black')
            return f'color: {color}'

        st.dataframe(keyword_summary.style.applymap(highlight_status, subset=['盈亏状态']))

        # 下载
        final_csv = keyword_summary.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载全周期汇总报表", final_csv, "LxU_Keyword_Analysis.csv", "text/csv")

else:
    st.info("请批量上传一段时间内的广告报表（如最近7天的多份报表）。")
