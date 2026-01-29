import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="LxU 广告全维度看板", layout="wide")

st.title("🚀 LxU 广告全维度看板")
st.markdown("集成指标：**真实ROAS、真实CPC、点击率、转化率、目标指标(%)**。")

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
        raw_df = pd.concat(all_data, ignore_index=True)import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="LxU 广告全维度看板", layout="wide")

st.title("🚀 LxU 广告全维度看板 (样式修复版)")
st.markdown("已修复：**总计行绿色高亮**回归，且达标时自动切换为**墨绿色**。")

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
            camp_name = str(row.iloc[5]) if len(row) > 5 else ""
            grp_name = str(row.iloc[6]) if len(row) > 6 else ""
            full_text = f"{camp_name} {grp_name}"
            p_code = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code.group(0).upper() if p_code else "未识别"
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = int(target_match.group(1)) if target_match else 0
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "汇总"
            return pd.Series([p_code, target_val, mod_date], index=['产品编号', '目标指标', '策略日期'])

        extracted_cols = raw_df.apply(extract_info, axis=1)
        raw_df = pd.concat([raw_df, extracted_cols], axis=1)

        # 3. 数据清洗重命名
        analysis_df = raw_df.copy()
        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面', 
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '展示量', 
            analysis_df.columns[14]: '点击量',
            analysis_df.columns[15]: '原支出', 
            analysis_df.columns[29]: '销量', 
            analysis_df.columns[32]: '销售额'
        })

        mask_ns = (analysis_df['关键词'].isna()) | \
                  (analysis_df['展示版面'].str.contains('비검색|非搜索', na=False)) | \
                  (analysis_df['关键词'].astype(str) == 'nan')
        
        analysis_df.loc[mask_ns, '关键词'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '展示版面'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '策略日期'] = '汇总'

        # 4. 指标计算
        def calculate_metrics(df):
            df['真实支出'] = (df['原支出'] * 1.1).round(0)
            df['真实ROAS'] = (df['销售额'] / df['真实支出'] * 100).round(2)
            df['真实CPC'] = (df['真实支出'] / df['点击量']).round(0)
            df['点击率'] = (df['点击量'] / df['展示量'] * 100).round(2)
            df['转化率'] = (df['销量'] / df['点击量'] * 100).round(2)
            return df.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 5. 聚合数据
        kw_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index()
        kw_summary = calculate_metrics(kw_summary)

        product_totals = kw_summary.groupby('产品编号').agg({
            '展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        product_totals = calculate_metrics(product_totals)

        # 6. 侧边栏筛选
        st.sidebar.header("📊 盈亏筛选器")
        status_filter = st.sidebar.radio("选择查看范围：", ["全部展示", "只看广告盈利 (ROAS达标)", "只看广告亏损 (ROAS不达标)"])
        if status_filter == "只看广告盈利 (ROAS达标)":
            valid_p_codes = product_totals[product_totals['真实ROAS'] >= product_totals['目标指标']]['产品编号'].tolist()
        elif status_filter == "只看广告亏损 (ROAS不达标)":
            valid_p_codes = product_totals[product_totals['真实ROAS'] < product_totals['目标指标']]['产品编号'].tolist()
        else:
            valid_p_codes = product_totals['产品编号'].tolist()

        # 7. 数据组装与样式逻辑
        unique_p = product_totals['产品编号'].unique()
        p_color_map = {p: '#f9f9f9' if i % 2 == 0 else '#ffffff' for i, p in enumerate(unique_p)}

        def apply_advanced_styles(row, is_tab1=True):
            p_code = row['产品编号']
            base_color = p_color_map.get(p_code, '#ffffff')
            
            # 判断行类型
            is_total = (row['维度'] == '📌 产品总计') if is_tab1 else (row['sort_weight'] == 2)
            is_ns = (row['维度'] == '🤖 非搜索区域') if is_tab1 else (row['sort_weight'] == 0)
            
            styles = []
            for col_name in row.index:
                cell_style = f'background-color: {base_color}'
                if is_total:
                    # 总计行默认浅绿
                    cell_style = 'background-color: #e8f4ea; font-weight: bold; border-top: 2px solid #ccc'
                    # 总计达标 -> 墨绿
                    if col_name == '真实ROAS' and row['目标指标'] > 0 and row['真实ROAS'] >= row['目标指标']:
                        cell_style = 'background-color: #2e7d32; color: #ffffff; font-weight: bold'
                elif is_ns:
                    cell_style = f'background-color: {base_color}; color: #0056b3; font-weight: 500'
                
                # 普通行达标
                if not is_total and col_name == '真实ROAS' and row['目标指标'] > 0 and row['真实ROAS'] >= row['目标指标']:
                    cell_style += '; background-color: #c6efce; color: #006100'
                styles.append(cell_style)
            return styles

        p_spend_map = product_totals.set_index('产品编号')['真实支出']

        # --- 布局展示 ---
        tab1, tab2 = st.tabs(["🎯 产品对比看板", "📄 关键词明细表"])
        
        with tab1:
            kw_f = kw_summary[kw_summary['产品编号'].isin(valid_p_codes)].copy()
            kw_f['维度'] = kw_f['关键词'].apply(lambda x: '🤖 非搜索区域' if '非搜索' in x else '🔎 搜索区域')
            area_df = kw_f.groupby(['产品编号', '维度']).agg({'展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'}).reset_index()
            area_df = calculate_metrics(area_df)
            area_df['支出占比'] = area_df.apply(lambda x: (x['真实支出'] / p_spend_map[x['产品编号']] * 100) if x['产品编号'] in p_spend_map else 0, axis=1).round(1)
            p_sub_f = product_totals[product_totals['产品编号'].isin(valid_p_codes)].copy()
            p_sub_f['维度'], p_sub_f['支出占比'] = '📌 产品总计', 100.0
            sheet1_df = pd.concat([area_df, p_sub_f], ignore_index=True).sort_values(['产品编号', '维度'], ascending=[True, False])
            
            st.dataframe(sheet1_df.style.apply(lambda r: apply_advanced_styles(r, True), axis=1), 
                         column_order=("产品编号", "维度", "目标指标", "真实ROAS", "支出占比", "真实支出", "销售额", "真实CPC", "点击率", "转化率"),
                         column_config={"真实ROAS": st.column_config.NumberColumn(format="%.2f%%"), "目标指标": st.column_config.NumberColumn(format="%d%%"), "支出占比": st.column_config.NumberColumn(format="%.1f%%")},
                         hide_index=True, use_container_width=True)

        with tab2:
            kw_f['sort_weight'] = kw_f['关键词'].apply(lambda x: 0 if '非搜索' in x else 1)
            det_sub = p_sub_f.rename(columns={'维度': '关键词'})
            det_sub['展示版面'], det_sub['策略日期'], det_sub['sort_weight'] = '📌 总计', 'TOTAL', 2
            sheet2_df = pd.concat([kw_f, det_sub], ignore_index=True).sort_values(['产品编号', 'sort_weight', '真实支出'], ascending=[True, True, False])
            sheet2_df['支出占比'] = sheet2_df.apply(lambda x: (x['真实支出'] / p_spend_map[x['产品编号']] * 100) if x['sort_weight'] != 2 else 100.0, axis=1).round(1)
            
            st.dataframe(sheet2_df.style.apply(lambda r: apply_advanced_styles(r, False), axis=1),
                         column_order=("产品编号", "展示版面", "关键词", "策略日期", "目标指标", "真实ROAS", "支出占比", "真实支出", "销售额", "真实CPC", "点击率", "转化率"),
                         column_config={"sort_weight": None, "真实ROAS": st.column_config.NumberColumn(format="%.2f%%"), "目标指标": st.column_config.NumberColumn(format="%d%%")},
                         hide_index=True, use_container_width=True, height=800)

        # 8. Excel 导出逻辑 (视觉效果同步)
        def to_excel_with_style(df1, df2):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                workbook = writer.book
                # 样式定义
                total_bg = workbook.add_format({'bg_color': '#e8f4ea', 'bold': True, 'border': 1})
                success_bg = workbook.add_format({'bg_color': '#2e7d32', 'font_color': '#ffffff', 'bold': True, 'border': 1})
                
                df1.to_excel(writer, sheet_name='Sheet1_产品对比看板', index=False)
                ws1 = writer.sheets['Sheet1_产品对比看板']
                for r_idx, (roas, target, dim) in enumerate(zip(df1['真实ROAS'], df1['目标指标'], df1['维度'])):
                    if dim == '📌 产品总计':
                        fmt = success_bg if (target > 0 and roas >= target) else total_bg
                        ws1.set_row(r_idx + 1, None, fmt)

                df2.drop(columns=['sort_weight', '维度'], errors='ignore').to_excel(writer, sheet_name='Sheet2_关键词详细明细', index=False)
                ws2 = writer.sheets['Sheet2_关键词详细明细']
                for r_idx, (roas, target, weight) in enumerate(zip(df2['真实ROAS'], df2['目标指标'], df2['sort_weight'])):
                    if weight == 2:
                        fmt = success_bg if (target > 0 and roas >= target) else total_bg
                        ws2.set_row(r_idx + 1, None, fmt)
            return output.getvalue()

        try:
            excel_data = to_excel_with_style(sheet1_df, sheet2_df)
            st.sidebar.download_button(label="📥 下载 LxU Excel 报告", data=excel_data, file_name="LxU_Ads.xlsx")
        except:
            st.sidebar.warning("请确保 requirements.txt 中包含 xlsxwriter")
else:
    st.info("👋 请上传报表。")

        # 2. 属性提取引擎
        def extract_info(row):
            camp_name = str(row.iloc[5]) if len(row) > 5 else ""
            grp_name = str(row.iloc[6]) if len(row) > 6 else ""
            full_text = f"{camp_name} {grp_name}"
            p_code = re.search(r'C\d{3,5}', full_text, re.IGNORECASE)
            p_code = p_code.group(0).upper() if p_code else "未识别"
            target_match = re.search(r'【(\d+)】', full_text)
            target_val = int(target_match.group(1)) if target_match else 0
            date_match = re.search(r'【(\d{1,2}\.\d{1,2})】', full_text)
            mod_date = date_match.group(1) if date_match else "汇总"
            return pd.Series([p_code, target_val, mod_date], index=['产品编号', '目标指标', '策略日期'])

        extracted_cols = raw_df.apply(extract_info, axis=1)
        raw_df = pd.concat([raw_df, extracted_cols], axis=1)

        # 3. 数据清洗与重命名
        analysis_df = raw_df.copy()
        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面', 
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '展示量', 
            analysis_df.columns[14]: '点击量',
            analysis_df.columns[15]: '原支出', 
            analysis_df.columns[29]: '销量', 
            analysis_df.columns[32]: '销售额'
        })

        mask_ns = (analysis_df['关键词'].isna()) | \
                  (analysis_df['展示版面'].str.contains('비검색|非搜索', na=False)) | \
                  (analysis_df['关键词'].astype(str) == 'nan')
        
        analysis_df.loc[mask_ns, '关键词'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '展示版面'] = '🤖 非搜索区域'
        analysis_df.loc[mask_ns, '策略日期'] = '汇总'

        # 4. 指标计算函数
        def calculate_metrics(df):
            df['真实支出'] = (df['原支出'] * 1.1).round(0)
            df['真实ROAS'] = (df['销售额'] / df['真实支出'] * 100).round(2)
            df['真实CPC'] = (df['真实支出'] / df['点击量']).round(0)
            df['点击率'] = (df['点击量'] / df['展示量'] * 100).round(2)
            df['转化率'] = (df['销量'] / df['点击量'] * 100).round(2)
            return df.replace([float('inf'), -float('inf')], 0).fillna(0)

        # 5. 聚合数据
        kw_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum'
        }).reset_index()
        kw_summary = calculate_metrics(kw_summary)

        product_totals = kw_summary.groupby('产品编号').agg({
            '展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'
        }).reset_index()
        product_totals = calculate_metrics(product_totals)

        # 6. 侧边栏筛选器
        st.sidebar.header("📊 盈亏筛选器")
        status_filter = st.sidebar.radio("选择查看范围：", ["全部展示", "只看广告盈利 (ROAS达标)", "只看广告亏损 (ROAS不达标)"])

        if status_filter == "只看广告盈利 (ROAS达标)":
            valid_p_codes = product_totals[product_totals['真实ROAS'] >= product_totals['目标指标']]['产品编号'].tolist()
        elif status_filter == "只看广告亏损 (ROAS不达标)":
            valid_p_codes = product_totals[product_totals['真实ROAS'] < product_totals['目标指标']]['产品编号'].tolist()
        else:
            valid_p_codes = product_totals['产品编号'].tolist()

        # --- 7. 数据组装 ---
        p_spend_map = product_totals.set_index('产品编号')['真实支出']
        
        # Sheet1: 对比看板
        kw_summary_f = kw_summary[kw_summary['产品编号'].isin(valid_p_codes)].copy()
        kw_summary_f['维度'] = kw_summary_f['关键词'].apply(lambda x: '🤖 非搜索区域' if '非搜索' in x else '🔎 搜索区域')
        area_df = kw_summary_f.groupby(['产品编号', '维度']).agg({'展示量': 'sum', '点击量': 'sum', '原支出': 'sum', '销量': 'sum', '销售额': 'sum', '目标指标': 'max'}).reset_index()
        area_df = calculate_metrics(area_df)
        area_df['支出占比'] = area_df.apply(lambda x: (x['真实支出'] / p_spend_map[x['产品编号']] * 100) if x['产品编号'] in p_spend_map else 0, axis=1).round(1)
        
        p_sub_f = product_totals[product_totals['产品编号'].isin(valid_p_codes)].copy()
        p_sub_f['维度'] = '📌 产品总计'
        p_sub_f['支出占比'] = 100.0
        sheet1_df = pd.concat([area_df, p_sub_f], ignore_index=True).sort_values(['产品编号', '维度'], ascending=[True, False])

        # Sheet2: 明细表
        kw_summary_f['sort_weight'] = kw_summary_f['关键词'].apply(lambda x: 0 if '非搜索' in x else 1)
        det_sub = p_sub_f.rename(columns={'维度': '关键词'})
        det_sub['展示版面'], det_sub['策略日期'], det_sub['sort_weight'] = '📌 总计', 'TOTAL', 2
        sheet2_df = pd.concat([kw_summary_f, det_sub], ignore_index=True).sort_values(['产品编号', 'sort_weight', '真实支出'], ascending=[True, True, False])
        sheet2_df['支出占比'] = sheet2_df.apply(lambda x: (x['真实支出'] / p_spend_map[x['产品编号']] * 100) if x['sort_weight'] != 2 else 100.0, axis=1).round(1)

        # 8. 视觉效果导出函数 (Excel)
        def to_excel_with_style(df1, df2):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # 写入样式定义
                workbook = writer.book
                total_fmt = workbook.add_format({'bg_color': '#e8f4ea', 'bold': True, 'border': 1})
                ns_fmt = workbook.add_format({'font_color': '#0056b3', 'bold': True})
                
                # 写入 Sheet1
                df1.to_excel(writer, sheet_name='Sheet1_产品对比看板', index=False)
                ws1 = writer.sheets['Sheet1_产品对比看板']
                for row_num, value in enumerate(df1['维度']):
                    if value == '📌 产品总计':
                        ws1.set_row(row_num + 1, None, total_fmt)
                    elif value == '🤖 非搜索区域':
                        ws1.write(row_num + 1, 1, value, ns_fmt)

                # 写入 Sheet2
                final_sheet2 = df2.drop(columns=['sort_weight', '维度'], errors='ignore')
                final_sheet2.to_excel(writer, sheet_name='Sheet2_关键词详细明细', index=False)
                ws2 = writer.sheets['Sheet2_关键词详细明细']
                for row_num, value in enumerate(df2['sort_weight']):
                    if value == 2:
                        ws2.set_row(row_num + 1, None, total_fmt)
                    elif value == 0:
                        ws2.write(row_num + 1, 2, '🤖 非搜索区域', ns_fmt)

            return output.getvalue()

        # 9. 界面展示
        tab1, tab2 = st.tabs(["🎯 产品对比看板", "📄 关键词明细表"])
        with tab1:
            st.dataframe(sheet1_df, use_container_width=True, hide_index=True)
        with tab2:
            st.dataframe(sheet2_df.drop(columns=['sort_weight', '维度'], errors='ignore'), use_container_width=True, hide_index=True, height=800)

        # 10. 下载按钮
        try:
            excel_data = to_excel_with_style(sheet1_df, sheet2_df)
            st.sidebar.download_button(
                label="📥 下载 LxU 广告分析报告 (Excel)",
                data=excel_data,
                file_name="LxU_Ad_Analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.sidebar.error(f"Excel 生成失败，请检查 requirements.txt: {e}")
else:
    st.info("👋 请上传报表。")

