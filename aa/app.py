import streamlit as st
import pandas as pd
import numpy as np
import io

# =================== 1. 数据清洗引擎 (适配东财原始数据粘贴) ===================

def clean_em_data(raw_text, mode="sector"):
    """
    清洗东财原始数据：自动提取核心列，忽略干扰列
    """
    try:
        # 处理粘贴文本
        df = pd.read_csv(io.StringIO(raw_text), sep=r'\s+', header=None, on_bad_lines='skip')
        
        def to_num(s):
            s = str(s).replace('%', '').replace('万', '').replace('亿', '').replace(',', '')
            return pd.to_numeric(s, errors='coerce')

        if mode == "sector":
            # 适配东财板块：名称(1), 今日涨幅(4), 今日主力净占比(12)
            processed = pd.DataFrame()
            processed['名称'] = df.iloc[:, 1]
            processed['今日涨幅'] = df.iloc[:, 4].apply(to_num)
            processed['主力占比'] = df.iloc[:, 12].apply(to_num)
            return processed.dropna(subset=['名称'])
        else:
            # 适配东财个股：名称(2), 主力净额(6)
            processed = pd.DataFrame()
            processed['名称'] = df.iloc[:, 2]
            processed['主力净额'] = df.iloc[:, 6].apply(to_num)
            return processed.dropna(subset=['名称'])
    except Exception as e:
        st.error(f"解析失败。请确保粘贴了东财整行数据。")
        return pd.DataFrame()

# =================== 2. 投行算法内核 (禁止删减) ===================

def run_sniffer_audit(df, mode="stock"):
    # 数值预处理
    cols = [c for c in df.columns if c != '名称']
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if mode == "sector":
        # First: L-H 象限审计 (占比>3%, 涨幅<2%)
        df['审计状态'] = np.where(
            (df['主力占比'] > 3.0) & (df['今日涨幅'] < 2.0), 
            "🚩 重点关注 (L-H扫货区)", 
            "待机"
        )
        return df.sort_values(by='主力占比', ascending=False)
    
    else:
        # Next: 穿透审计 [Ea, Sm, Signal]
        # Ea 吸筹效率 (成交量/振幅补位处理)
        df['Ea'] = df['今日主力'] / (10000 * (2.0 + 0.1)) 
        
        # Sm 持仓稳定性 (权重：0.5, 0.3, 0.2)
        df['weighted_sum'] = df['今日主力']*0.5 + df['5日主力']*0.3 + df['10日主力']*0.2
        df['std_flow'] = df.apply(lambda x: np.std([x['今日主力'], x['5日主力'], x['10日主力']]), axis=1)
        df['Sm'] = df['weighted_sum'] / (df['std_flow'] + 1)
        
        # Signal 爆发点识别 (今日+, 5日-, 10日-)
        df['is_target'] = (df['今日主力'] > 0) & (df['5日主力'] < 0) & (df['10日主力'] < 0)
        df['审计状态'] = np.where(df['is_target'], "💎 爆发点确认", "洗盘中")
        
        return df.sort_values(by='Ea', ascending=False)

# =================== 3. UI 界面设计 ===================

st.set_page_config(page_title="Sniffer 嗅嗅 Audit Terminal", layout="wide")
st.title("🏛️ Sniffer 嗅嗅 - 投行数据审计终端")

# --- Step 1: 板块初筛 ---
st.header("Step 1: First - 板块 L-H 象限确认")
sector_input = st.text_area("📥 粘贴东财板块行情 (整行数据)", height=150)

if sector_input:
    sec_base = clean_em_data(sector_input, mode="sector")
    if not sec_base.empty:
        sec_res = run_sniffer_audit(sec_base, mode="sector")
        # 使用文字展示判语
        st.table(sec_res[['名称', '今日涨幅', '主力占比', '审计状态']])

# --- Step 2: 个股多周期穿透 ---
st.divider()
st.header("Step 2: Next - 个股多周期穿透")
st.info("💡 依次粘贴个股 今日 / 5日 / 10日 的排行榜数据")

c1, c2, c3 = st.columns(3)
with c1: in_t = st.text_area("1. 粘贴今日资金流", height=150)
with c2: in_5 = st.text_area("2. 粘贴5日资金流", height=150)
with c3: in_10 = st.text_area("3. 粘贴10日资金流", height=150)

if in_t and in_5 and in_10:
    df_t = clean_em_data(in_t, mode="stock").rename(columns={'主力净额':'今日主力'})
    df_5 = clean_em_data(in_5, mode="stock").rename(columns={'主力净额':'5日主力'})
    df_10 = clean_em_data(in_10, mode="stock").rename(columns={'主力净额':'10日主力'})
    
    try:
        # 自动对齐合并
        m = pd.merge(df_t, df_5, on='名称')
        m = pd.merge(m, df_10, on='名称')
        
        st_res = run_sniffer_audit(m, mode="stock")
        st.table(st_res[['名称', 'Ea', 'Sm', '审计状态']])
        
        targets = st_res[st_res['is_target'] == True]['名称'].tolist()
        if targets:
            st.success(f"🎯 爆发点审计通过：{', '.join(targets)}")
            st.warning("⚠️ Finally: 请配合 15 分钟 K 线缩量上涨进行最后确权")
    except:
        st.error("数据对齐失败，请确保三个周期内都有相同的股票。")
