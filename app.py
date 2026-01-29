import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="LxU 广告报表分析助手", layout="wide")

st.title("📊 Coupang 广告数据分析工具")
st.markdown("上传您的广告报表 (CSV/Excel)，自动生成多维度分析报告。")

# 1. 文件上传
uploaded_file = st.file_uploader("选择报表文件", type=['csv', 'xlsx'])

if uploaded_file:
    # 自动识别格式读取
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # 2. 数据清洗 (根据 Coupang 报表字段调整)
    # 注意：需根据你实际下载的报表语言（韩文/中文/英文）匹配字段名
    st.sidebar.header("数据筛选")
    
    # 示例字段映射（请根据实际报表修改列名）
    # 假设字段包含：'광고명', '노출수', '클릭수', '광고비', '총매출'
    
    # 计算核心指标
    if '광고비' in df.columns and '총매출' in df.columns:
        df['ROAS (%)'] = (df['총매출'] / df['광고비']) * 100
        df['CTR (%)'] = (df['클릭수'] / df['노출수']) * 100
        df['CPC'] = df['광고비'] / df['클릭수']

    # 3. 数据看板展示
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总消耗", f"₩{df['광고비'].sum():,.0f}")
    with col2:
        st.metric("总销售额", f"₩{df['총매출'].sum():,.0f}")
    with col3:
        avg_roas = (df['총매출'].sum() / df['광고비'].sum()) * 100
        st.metric("平均 ROAS", f"{avg_roas:.2f}%")
    with col4:
        st.metric("总点击量", f"{df['클릭수'].sum():,.0f}")

    # 4. 可视化图表
    st.subheader("广告趋势分析")
    fig = px.scatter(df, x="광고비", y="총매출", size="클릭수", color="ROAS (%)",
                     hover_name=df.columns[0], title="消耗 vs 销售额 (气泡大小代表点击数)")
    st.plotly_chart(fig, use_container_寬度=True)

    # 5. 明细数据
    st.subheader("详细数据报表")
    st.dataframe(df)

else:
    st.info("💡 请先上传从 Coupang 广告后台导出的报表文件。")