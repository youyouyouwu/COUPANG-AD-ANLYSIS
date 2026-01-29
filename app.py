import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告全维度汇总", layout="wide")

st.title("📈 关键词与版面全周期汇总")
st.markdown("已加入：**非搜索区域**汇总逻辑。M列为空的数据将自动标记并计算。")

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

        # 1. 属性提取函数
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

        # 2. 列名映射与预处理
        analysis_df = raw_df.copy()
        
        # 特殊处理 M 列（关键词）：如果为空，则根据 L 列或直接标记为非搜索区域
        # M列索引为 12，L列索引为 11
        analysis_df.iloc[:, 12] = analysis_df.iloc[:, 12].fillna("非搜索区域")

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面', # L列
            analysis_df.columns[12]: '关键词',   # M列
            analysis_df.columns[13]: '总展示',   # N列
            analysis_df.columns[14]: '总点击',   # O列
            analysis_df.columns[15]: '原始广告费', # P列
            analysis_df.columns[29]: '总销量(单数)', # AD列
            analysis_df.columns[32]: '总转化销售额'  # AG列
        })

        # 3. 执行全周期聚合
        # 增加“展示版面”作为聚合维度，这样可以区分 关键词 和 非搜索区域
        keyword_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '总展示': 'sum',
            '总点击': 'sum',
            '原始广告费': 'sum',
            '总销量(单数)': 'sum',
            '总转化销售额': 'sum'
        }).reset_index()

        # 4. 指标计算
        keyword_summary['真实广告费(含税)'] = (keyword_summary['原始广告费'] * 1.1).round(0)
        keyword_summary['真实ROAS'] = (keyword_summary['总转化销售额'] / keyword_summary['真实广告费(含税)'] * 100).round(2)
        keyword_summary['真实点击率'] = (keyword_summary['总点击'] / keyword_summary['总展示'] * 100).round(2)
        keyword_summary['真实CPC'] = (keyword_summary['真实广告费(含税)'] / keyword_summary['总点击']).round(0)

        keyword_summary = keyword_summary.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 5. 盈亏状态判定
        def check_status(row):
            if row['目标指标'] == 0: return "未设目标"
            return "✅ 达标" if row['真实ROAS'] >= row['目标指标'] else "❌ 亏损"
        
        keyword_summary['盈亏状态'] = keyword_summary.apply(check_status, axis=1)

        # --- 界面展示 ---
        st.success(f"✅ 汇总完成！已包含“非搜索区域”数据的统计。")

        # 筛选器
        st.sidebar.header("数据筛选")
        area_filter = st.sidebar.multiselect("版面筛选", options=keyword_summary['展示版面'].unique(), default=keyword_summary['展示版面'].unique())
        if area_filter:
            keyword_summary = keyword_summary[keyword_summary['展示版面'].isin(area_filter)]

        # 格式化显示
        st.dataframe(
            keyword_summary,
            column_config={
                "目标指标": st.column_config.NumberColumn("目标指标", format="%d%%"),
                "真实ROAS": st.column_config.NumberColumn("真实ROAS", format="%.2f%%"),
                "真实点击率": st.column_config.NumberColumn("真实点击率", format="%.2f%%"),
                "总转化销售额": st.column_config.NumberColumn("总转化销售额", format="₩%d"),
                "真实广告费(含税)": st.column_config.NumberColumn("真实广告费(含税)", format="₩%d"),
                "真实CPC": st.column_config.NumberColumn("真实CPC", format="₩%d")
            },
            hide_index=True,
            use_container_width=True
        )

        # 下载
        final_csv = keyword_summary.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载含非搜索区域报表", final_csv, "LxU_Full_Area_Report.csv", "text/csv")

else:
    st.info("请批量上传广告报表。")
