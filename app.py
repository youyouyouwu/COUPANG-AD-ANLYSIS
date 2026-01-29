import streamlit as st
import pandas as pd
import re

# ... (上传文件的部分保持不变)

    if all_data:
        raw_df = pd.concat(all_data, ignore_index=True)

        # 1. 提取产品编号、目标指标等 (这一步保持原样)
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

        # 2. 【重点修复】：数据清洗与统一化
        analysis_df = raw_df.copy()

        # 统一处理 M列(关键词) 和 L列(展示版面)
        # 将空值填充为字符串，并去掉前后的不可见空格
        analysis_df.iloc[:, 12] = analysis_df.iloc[:, 12].astype(str).str.strip().replace({'nan': '非搜索区域', '': '非搜索区域'})
        analysis_df.iloc[:, 11] = analysis_df.iloc[:, 11].astype(str).str.strip()

        # 再次确认：如果关键词被标记为“非搜索区域”，则版面也统一，防止聚合分裂
        analysis_df.loc[analysis_df.iloc[:, 12] == '非搜索区域', analysis_df.columns[11]] = '非搜索区域'

        analysis_df = analysis_df.rename(columns={
            analysis_df.columns[11]: '展示版面',
            analysis_df.columns[12]: '关键词',
            analysis_df.columns[13]: '总展示',
            analysis_df.columns[14]: '总点击',
            analysis_df.columns[15]: '原始广告费',
            analysis_df.columns[29]: '总销量(单数)',
            analysis_df.columns[32]: '总转化销售额'
        })

        # 3. 聚合计算 (现在 '非搜索区域' 的字符串完全一致，会被合并)
        keyword_summary = analysis_df.groupby(['产品编号', '展示版面', '关键词', '目标指标', '策略日期']).agg({
            '总展示': 'sum',
            '总点击': 'sum',
            '原始广告费': 'sum',
            '总销量(单数)': 'sum',
            '总转化销售额': 'sum'
        }).reset_index()

        # 4. 后续计算：真实广告费、ROAS、支出占比
        keyword_summary['真实广告费(含税)'] = (keyword_summary['原始广告费'] * 1.1).round(0)
        
        # 计算产品总支出用于占比
        total_spend_map = keyword_summary.groupby('产品编号')['真实广告费(含税)'].transform('sum')
        keyword_summary['支出占比'] = (keyword_summary['真实广告费(含税)'] / total_spend_map * 100).round(2)

        keyword_summary['真实ROAS'] = (keyword_summary['总转化销售额'] / keyword_summary['真实广告费(含税)'] * 100).round(2)
        keyword_summary['真实点击率'] = (keyword_summary['总点击'] / keyword_summary['总展示'] * 100).round(2)
        keyword_summary['真实CPC'] = (keyword_summary['真实广告费(含税)'] / keyword_summary['总点击']).round(0)

        # ... (盈亏判定和界面展示代码保持不变)
