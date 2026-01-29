import streamlit as st
import pandas as pd

st.set_page_config(page_title="LxU 广告汇总工具", layout="wide")

st.title("📊 Coupang 多店铺广告数据合并")

# 1. 多文件上传
uploaded_files = st.file_uploader(
    "批量上传广告报表", 
    type=['csv', 'xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # 根据后缀读取，并处理韩文编码
            if file.name.endswith('.csv'):
                try:
                    df = pd.read_csv(file, encoding='utf-8')
                except:
                    df = pd.read_csv(file, encoding='cp949')
            else:
                df = pd.read_excel(file)
            
            # 记录来源文件名，方便区分店铺
            df['数据来源文件'] = file.name
            all_data.append(df)
        except Exception as e:
            st.error(f"文件 {file.name} 读取失败: {e}")

    if all_data:
        # 2. 合并数据
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # 3. 存入 Session State 供后续步骤使用
        st.session_state['raw_df'] = combined_df
        
        st.success(f"✅ 成功合并 {len(uploaded_files)} 个文件！总行数: {len(combined_df)}")
        
        # 展示前 10 行预览
        st.subheader("合并数据预览")
        st.dataframe(combined_df.head(10))
        
        # 侧边栏：列出检测到的字段名，方便我们下一步定位
        st.sidebar.write("### 检测到的原始字段：")
        st.sidebar.write(list(combined_df.columns))
        
else:
    st.info("👋 请上传一个或多个 Coupang 报表文件开始测试。")
