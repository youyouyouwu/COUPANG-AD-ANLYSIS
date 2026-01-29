import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告投放比例分析", layout="wide")

st.title("📈 广告投放比例与关键词分析")
st.markdown("计算每个关键词及**非搜索区域**在所属产品中的支出比例，监控 Coupang 流量分布。")

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

        # 2. 列名映射与关键词清洗
        analysis_df = raw_df.copy()
        analysis_df.iloc[:, 12] = analysis_df.iloc[:, 12].fillna("非搜索区域")

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面',
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '总展示',
            analysis_df.columns[14]: '总点击',
            analysis_df.columns[15]: '原始广告费',
            analysis_df.columns[29]: '总销量(单数)',
            analysis_df.columns[32]: '总转化销售额'
        })

        # 3. 聚合计算
        keyword_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '总展示': 'sum',
            '总点击': 'sum',
            '原始广告费': 'sum',
            '总销量(单数)': 'sum',
            '总转化销售额': 'sum'
        }).reset_index()

        # 计算含税支出
        keyword_summary['真实广告费(含税)'] = (keyword_summary['原始广告费'] * 1.1).round(0)

        # --- 核心改进：计算支出占比 ---
        # 1. 计算每个产品的总支出
        product_total_spend = keyword_summary.groupby('产品编号')['真实广告费(含税)'].transform('sum')
        # 2. 计算占比
        keyword_summary['支出占比'] = (keyword_summary['真实广告费(含税)'] / product_total_spend * 100).round(2)

        # 4. 指标二次计算
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
        st.success("✅ 比例分析完成！您可以查看各词及非搜索区域的预算分配。")

        # 数据预览与美化
        st.dataframe(
            keyword_summary,
            column_config={
                "支出占比": st.column_config.NumberColumn("支出占比", format="%.2f%%"),
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

        # 新增可视化：非搜索区域占比图
        st.divider()
        st.subheader("💡 投放比例可视化")
        
        # 提取非搜索区域占比
        non_search_data = keyword_summary[keyword_summary['展示版面'] == '비검색 영역'].copy() # 注意韩文报表原词
        if non_search_data.empty:
            non_search_data = keyword_summary[keyword_summary['关键词'] == '非搜索区域'].copy()

        if not non_search_data.empty:
            st.bar_chart(non_search_data.set_index('产品编号')['支出占比'])
            st.info("上方图表显示了每个产品中“非搜索区域”占用的预算百分比。")

        # 下载
        final_csv = keyword_summary.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载完整占比分析报表", final_csv, "LxU_Spend_Share_Report.csv", "text/csv")

else:
    st.info("请批量上传广告报表。")
