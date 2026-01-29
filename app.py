import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告清洗分析 - 进阶版", layout="wide")

st.title("📊 广告报表多维度清洗")
st.markdown("已加入：**产品编号**、**目标指标**、**策略日期** 的自动提取功能。")

uploaded_files = st.file_uploader("批量上传报表", type=['csv', 'xlsx'], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            df = pd.read_csv(file, encoding='cp949') if file.name.endswith('.csv') else pd.read_excel(file)
            all_data.append(df)
        except:
            # 备选编码处理
            df = pd.read_csv(file, encoding='utf-8-sig')
            all_data.append(df)

    if all_data:
        raw_df = pd.concat(all_data, ignore_index=True)

        def extract_info(row):
            # 获取 F列(索引5) 和 G列(索引6)
            camp_name = str(row.iloc[5]) if len(row) > 5 else ""
            grp_name = str(row.iloc[6]) if len(row) > 6 else ""
            full_text = f"{camp_name} {grp_name}"

            # 1. 提取产品编号 (C001, C0001)
            code_match = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = code_match.group(0).upper() if code_match else "未识别"

            # 2. 提取目标指标 (匹配 【409】 这种纯数字)
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = target_match.group(1) if target_match else "未设置"

            # 3. 提取改动日期 (匹配 【5.22】 这种带点的日期)
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "未知日期"

            return pd.Series([p_code, target_val, mod_date])

        # 应用提取
        st.info("🔍 正在深度解析广告名称中的嵌入属性...")
        raw_df[['产品编号', '目标指标', '策略日期']] = raw_df.apply(extract_info, axis=1)

        # 整理列顺序：将新提取的属性放在最前面
        new_cols = ['产品编号', '目标指标', '策略日期']
        other_cols = [c for c in raw_df.columns if c not in new_cols]
        cleaned_df = raw_df[new_cols + other_cols]

        # --- 界面展示 ---
        st.success("✅ 多维度特征提取完成！")
        
        # 数据统计仪表盘
        c1, c2, c3 = st.columns(3)
        c1.metric("识别产品数", len(cleaned_df['产品编号'].unique()))
        c2.metric("已设目标广告数", len(cleaned_df[cleaned_df['目标指标'] != "未设置"]))
        c3.metric("最近策略日期", cleaned_df['策略日期'].max() if not cleaned_df.empty else "-")

        st.subheader("清洗后结果（前50行）")
        st.dataframe(cleaned_df.head(50))

        # 下载区域
        csv_data = cleaned_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载完整清洗报表", csv_data, "LxU_Cleaned_Report.csv", "text/csv")
        
        st.session_state['cleaned_df'] = cleaned_df

else:
    st.info("请上传文件开始深度清洗。")
