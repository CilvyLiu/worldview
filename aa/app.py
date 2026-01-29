import streamlit as st
import pandas as pd
import numpy as np
import io

# =================== 1. 投行公式计算内核 (禁止删减) ===================

def run_sniffer_audit(df, mode="stock"):
    # 强制数值化处理
    for col in df.columns:
        if col not in ['名称', '代码', '审计判语']:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
    
    if mode == "sector":
        # First: L-H 扫货区判断
        df['L-H预警'] = (df['主力占比'] > 3.0) & (df['今日涨幅'] < 2.0)
        return df.sort_values(by='主力占比', ascending=False)
    
    else:
        # Next: 个股审计逻辑
        df['Ea'] = df['今日主力'] / (df['成交量'] * (df['振幅'] + 0.1))
        df['weighted_sum'] = df['今日主力']*0.5 + df['5日主力']*0.3 + df['10日主力']*0.2
        df['std_flow'] = df.apply(lambda x: np.std([x['今日主力'], x['5日主力'], x['10日主力']]), axis=1)
        df['Sm'] = df['weighted_sum'] / (df['std_flow'] + 1)
        # Signal: 爆发点识别 (今日+, 5日-, 10日-)
        df['Signal'] = (df['今日主力'] > 0) & (df['5日主力'] < 0) & (df['10日主力'] < 0)
        return df.sort_values(by='Ea', ascending=False)

# =================== 2. UI 渲染逻辑 (颜色控制) ===================

def style_sector(row):
    """板块表格整行变色逻辑"""
    return ['background-color: #d4edda; color: #155724' if row['L-H预警'] else '' for _ in row]

def style_stock(row):
    """个股表格整行变色逻辑"""
    if row['Signal']:
        return ['background-color: #f8d7da; color: #721c24; font-weight: bold' for _ in row]
    return ['' for _ in row]

# =================== 3. 页面布局 ===================

st.set_page_config(page_title="Sniffer 嗅嗅 Audit Terminal", layout="wide")
st.title("🏛️ Sniffer 嗅嗅 - 投行数据审计终端")

# --- Step 1: 板块 ---
st.header("Step 1: First - 板块初筛")
sector_input = st.text_area("📋 粘贴板块数据 (名称 | 今日涨幅 | 主力占比)", height=150)

if sector_input:
    try:
        sec_df = pd.read_csv(io.StringIO(sector_input), sep=r'\s+', names=['名称', '今日涨幅', '主力占比'], on_bad_lines='skip')
        sec_res = run_sniffer_audit(sec_df, mode="sector")
        st.write("🚩 绿色行 = L-H 扫货预警区（占比 > 3%, 涨幅 < 2%）")
        st.dataframe(sec_res.style.apply(style_sector, axis=1), use_container_width=True)
    except: st.error("板块数据格式有误，请检查。")

# --- Step 2: 个股 ---
st.divider()
st.header("Step 2: Next - 个股穿透")
stock_input = st.text_area("📋 粘贴个股数据 (名称 | 今日主力 | 5日主力 | 10日主力 | 成交量 | 振幅)", height=200)

if stock_input:
    try:
        st_df = pd.read_csv(io.StringIO(stock_input), sep=r'\s+', names=['名称', '今日主力', '5日主力', '10日主力', '成交量', '振幅'], on_bad_lines='skip')
        st_res = run_sniffer_audit(st_df, mode="stock")
        st.write("🚩 浅红行 = Signal 爆发点（今日反转，长线洗盘已久）")
        st.dataframe(st_res[['名称', 'Ea', 'Sm', 'Signal']].style.apply(style_stock, axis=1), use_container_width=True)
        
        targets = st_res[st_res['Signal'] == True]['名称'].tolist()
        if targets:
            st.success(f"🎯 爆发点审计通过：{', '.join(targets)}")
            st.warning("⚠️ Finally: 请手动确认 15 分钟 K 线缩量上涨！")
    except: st.error("个股数据格式有误。")
