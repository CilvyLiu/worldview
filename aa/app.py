import streamlit as st
import pandas as pd
import numpy as np
import re

# =================== 1. 智能清洗引擎 (自动识别金额与占比) ===================

def to_num(s):
    """处理千分位、百分号及亿万单位"""
    if pd.isna(s): return 0.0
    s = str(s).strip().replace(',', '').replace('%', '')
    match = re.search(r'[-+]?\d*\.?\d+', s)
    if not match: return 0.0
    val = float(match.group())
    if '亿' in s: val *= 1e8
    if '万' in s: val *= 1e4
    return val

def clean_em_data(raw_text, mode="sector"):
    try:
        lines = [l.strip() for l in raw_text.strip().split('\n') if l.strip()]
        lines = [l for l in lines if not re.search(r'名称|代码|涨幅|主力|占比|序号', l)]
        data = [re.split(r'\s+', l) for l in lines]
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame()

        processed = pd.DataFrame()
        
        if mode == "sector":
            # 1. 提取名称 (通常在第2列)
            processed['名称'] = df.iloc[:, 1]
            # 2. 寻找涨幅列 (带百分号或数值较小的列)
            processed['今日涨幅'] = df.iloc[:, 3].apply(to_num)
            
            # 3. 智能定位占比列：遍历可能的列，寻找数值在 0-100 之间的作为占比
            # 避免误抓动辄数亿的“主力净流入”金额列
            col_4 = df.iloc[:, 4].apply(to_num)
            col_5 = df.iloc[:, 5].apply(to_num)
            
            # 逻辑：占比通常不会超过 100%，金额通常极大
            processed['主力占比'] = np.where(col_5.abs() < 100, col_5, col_4)
            # 如果抓到的还是金额，强行修正
            processed['主力占比'] = processed['主力占比'].apply(lambda x: x if abs(x) < 100 else 0.0)
            
            return processed.dropna(subset=['名称'])
        else:
            # 个股模式：适配表头索引
            processed['代码'] = df.iloc[:, 1].astype(str)
            processed['名称'] = df.iloc[:, 2]
            # 寻找主力净额 (数值通常很大)
            processed['主力净额'] = df.iloc[:, 6].apply(to_num)
            return processed.dropna(subset=['名称'])
            
    except Exception as e:
        return pd.DataFrame()

# =================== 2. 投行审计内核 (First -> Next) ===================

def run_sniffer_audit(df, mode="stock"):
    numeric_cols = [c for c in df.columns if c not in ['名称', '代码', '审计状态']]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if mode == "sector":
        # First: L-H 扫货区审计 (Nova 指令：占比>3%, 涨幅<2%)
        # 增加上限约束，防止误抓金额
        df['审计状态'] = np.where(
            (df['主力占比'] > 3.0) & (df['主力占比'] < 100.0) & (df['今日涨幅'] < 2.0), 
            "🚩 重点关注 (L-H扫货区)", 
            "待机"
        )
        return df.sort_values(by='主力占比', ascending=False)
    
    else:
        # Next: 穿透审计 [Ea, Sm, Signal]
        df['Ea'] = df['今日主力'] / (10000 * 2.1) 
        df['weighted_sum'] = df['今日主力']*0.5 + df['5日主力']*0.3 + df['10日主力']*0.2
        df['std_flow'] = df.apply(lambda x: np.std([x['今日主力'], x['5日主力'], x['10日主力']]), axis=1)
        df['Sm'] = df['weighted_sum'] / (df['std_flow'] + 1)
        
        # Signal 爆发点识别
        df['is_target'] = (df['今日主力'] > 0) & (df['5日主力'] < 0) & (df['10日主力'] < 0)
        
        def get_label(row):
            if row['is_target']: return "💎 爆发点确认"
            if row['今日主力'] > 0 and row['5日主力'] > 0: return "📈 持续吸筹"
            return "洗盘中"
            
        df['审计状态'] = df.apply(get_label, axis=1)
        return df.sort_values(by='Ea', ascending=False)

# =================== 3. UI 界面设计 ===================

st.set_page_config(page_title="Sniffer Pro", layout="wide")
st.title("🏛️ Sniffer 嗅嗅 - 投行数据审计终端")

st.header("Step 1: First")
sector_input = st.text_area("📥 粘贴板块行情全行数据", height=100)
if st.button("🚀 执行板块初筛审计", use_container_width=True):
    if sector_input:
        res = run_sniffer_audit(clean_em_data(sector_input, mode="sector"), mode="sector")
        if not res.empty:
            st.table(res[['名称', '今日涨幅', '主力占比', '审计状态']])

st.divider()

st.header("Step 2: Next")
st.caption("提示：依次粘贴目标板块个股的 今日/5日/10日 资金榜单")
c1, c2, c3 = st.columns(3)
with c1: in_t = st.text_area("1. 今日资金榜", height=120)
with c2: in_5 = st.text_area("2. 5日资金榜", height=120)
with c3: in_10 = st.text_area("3. 10日资金榜", height=120)

if st.button("🔍 执行深度穿透审计", use_container_width=True):
    if in_t and in_5 and in_10:
        dt = clean_em_data(in_t, mode="stock").rename(columns={'主力净额':'今日主力'})
        d5 = clean_em_data(in_5, mode="stock").rename(columns={'主力净额':'5日主力'})
        d10 = clean_em_data(in_10, mode="stock").rename(columns={'主力净额':'10日主力'})
        try:
            m = pd.merge(dt, d5, on=['代码','名称']).merge(d10, on=['代码','名称'])
            res = run_sniffer_audit(m, mode="stock")
            st.table(res[['名称', '代码', 'Ea', 'Sm', '审计状态']])
            
            targets = res[res['审计状态'] == "💎 爆发点确认"]['名称'].tolist()
            if targets:
                st.success(f"🎯 潜伏目标锁定：{', '.join(targets)}")
                st.warning("⚠️ Finally: 请确认 15 分钟 K 线缩量上涨形态！")
        except:
            st.error("对齐失败。请确保三个框粘贴的是同一板块的数据清单。")
