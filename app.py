import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="LxU 广告数据清洗助手", layout="wide")

st.title("📊 广告报表归类与清洗")

# 1. 文件上传
uploaded_files = st.file_uploader(
    "批量上传广告报表", 
    type=['csv', 'xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            if file.name.endswith('.csv'):
                try:
                    df = pd.read_csv(file, encoding='utf-8')
                except:
                    df = pd.read_csv(file, encoding='cp949')
            else:
                df = pd.read_excel(file)
            all_data.append(df)
        except Exception as e:
            st.error(f"文件 {file.name} 读取失败: {e}")

    if all_data:
        raw_df = pd.concat(all_data, ignore_index=True)
        
        # --- 第二步：提取产品编号逻辑 ---
        
        # 提取编号的函数：匹配 C + 数字 (例如 C001, C0001)
        def extract_product_code(row):
            # 获取 F列(索引5) 和 G列(索引6) 的内容
            # 使用 try-except 防止列索引越界或数据非字符串
            try:
                campaign_name = str(row.iloc[5]) if len(row) > 5 else ""
                ad_group_name = str(row.iloc[6]) if len(row) > 6 else ""
                
                # 合并两列文本进行搜索
                combined_text = f"{campaign_name} {ad_group_name}"
                
                # 正则表达式说明: C 后面接 3 到 5 位数字
                match = re.search(r'C\d{3,5}', combined_text, re.IGNORECASE)
                return match.group(0).upper() if match else "未识别编号"
            except:
                return "解析异常"

        st.info("正在根据广告活动名称(F列)和广告组名称(G列)提取产品编号...")
        
        # 应用提取函数
        raw_df['产品编号'] = raw_df.apply(extract_product_code, axis=1)
        
        # --- 第三步：数据整理 ---
        
        # 将“产品编号”移到表格第一列方便查看
        cols = ['产品编号'] + [col for col in raw_df.columns if col != '产品编号']
        cleaned_df = raw_df[cols]
        
        st.success(f"✅ 处理完成！总记录: {len(cleaned_df)}")
        
        # 统计识别情况
        stats = cleaned_df['产品编号'].value_counts()
        st.sidebar.subheader("产品编号统计")
        st.sidebar.write(stats)

        # 预览数据
        st.subheader("清洗后数据预览 (已识别产品编号)")
        st.dataframe(cleaned_df)
        
        # 导出功能
        st.subheader("导出整理后的报表")
        csv = cleaned_df.to_csv(index=False).encode('utf-8-sig') # utf-8-sig 解决Excel打开乱码
        st.download_button(
            label="📥 下载整理后的表格 (.csv)",
            data=csv,
            file_name='cleaned_ads_report.csv',
            mime='text/csv',
        )
        
        # 存入 session_state 供下一步分析使用
        st.session_state['cleaned_df'] = cleaned_df

else:
    st.info("👋 请先批量上传广告报表进行整理。")
