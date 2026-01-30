import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# =================== 1. 强力数据清洗引擎 (严格对齐附件表头) ===================

def to_num(s):
    """极致兼容：处理 14.38亿, 3.12%, -218,000.00"""
    if pd.isna(s): return 0.0
    s = str(s).strip().replace(',', '').replace('%', '')
    match = re.search(r'[-+]?\d*\.?\d+', s)
    if not match: return 0.0
    val = float(match.group())
    if '亿' in s: val *= 1e8
    if '万' in s: val *= 1e4
    return val

def clean_em_data(raw_text, mode="sector"):
    """
    根据附件表头物理位置取值：
    板块：索引1名称, 索引3涨幅, 索引5占比
    个股：索引1代码, 索引2名称, 索引6净额
    """
    try:
        lines = [l.strip() for l in raw_text.strip().split('\n') if l.strip()]
        # 过滤干扰行
        lines = [l for l in lines if not re.search(r'名称|代码|涨幅|主力|占比|序号', l)]
        
        data = [re.split(r'\s+', l) for l in lines]
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame()

        processed = pd.DataFrame()
        
        if mode == "sector":
            # 适配板块附件表头
            processed['名称'] = df.iloc[:, 1]
            processed['今日涨幅'] = df.iloc[:, 3].apply(to_num)
            processed['主力占比'] = df.iloc[:, 5].apply(to_num)
            return processed.dropna(subset=['名称'])
        else:
            # 适配个股附件表头
            processed['代码'] = df.iloc[:, 1].astype(str)
            processed['名称'] = df.iloc[:, 2]
            processed['主力净额'] = df.iloc[:, 6].apply(to_num)
            return processed.dropna(subset=['名称'])
            
    except Exception as e:
        return pd.DataFrame()

# =================== 2. 投行审计内核 (First -> Next) ===================

def run_sniffer_audit(df, mode="stock"):
    # 数值化预处理
    numeric_cols = [c for c in df.columns if c not in ['名称', '代码', '审计状态']]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if mode == "sector":
        # First: L-H 扫货区审计 (Nova 指令：占比>3%, 涨幅<2%)
        df['审计状态'] = np.where(
            (df['主力占比'] > 3.0) & (df['今日涨幅'] < 2.0), 
            "🚩 重点关注 (L-H扫货区)", 
            "待机"
        )
        return df.sort_values(by='主力占比', ascending=False)
    
    else:
        # Next: 穿透审计 [Ea, Sm, Signal]
        # Ea 吸筹效率：单位亿级换算
        df['Ea'] = df['今日主力'] / (10000 * 2.1) 
        
        # Sm 持仓稳定性 (权重：今日0.5, 5日0.3, 10日0.2)
        df['weighted_sum'] = df['今日主力']*0.5 + df['5日主力']*0.3 + df['10日主力']*0.2
        df['std_flow'] = df.apply(lambda x: np.std([x['今日主力'], x['5日主力'], x['10日主力']]), axis=1)
        df['Sm'] = df['weighted_sum'] / (df['std_flow'] + 1)
        
        # Signal 爆发点识别 (今日净流入 + 前期洗盘)
        df['is_target'] = (df['今日主力'] > 0) & (df['5日主力'] < 0) & (df['10日主力'] < 0)
        
        def get_label(row):
            if row['is_target']: return "💎 爆发点确认"
            if row['今日主力'] > 0 and row['5日主力'] > 0: return "📈 持续吸筹"
            return "洗盘中"
            
        df['审计状态'] = df.apply(get_label, axis=1)
        return df.sort_values(by='Ea', ascending=False)

# =================== 3. UI 界面设计 (移动端优化) ===================

st.set_page_config(page_title="Sniffer Pro", layout="wide")
st.title("🏛️ Sniffer 嗅嗅 - 投行数据审计终端")

# Step 1: 板块初筛
st.header("Step 1: First")
sector_input = st.text_area("📥 粘贴板块行情全行数据", height=100, placeholder="粘贴此处...")
if st.button("🚀 执行板块初筛审计", use_container_width=True):
    if sector_input:
        res = run_sniffer_audit(clean_em_data(sector_input, mode="sector"), mode="sector")
        if not res.empty:
            st.table(res[['名称', '今日涨幅', '主力占比', '审计状态']])
        else:
            st.warning("未能识别数据，请检查复制内容是否包含表头下的数据行。")

st.divider()

# Step 2: 个股穿透
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
            # 核心对齐：代码+名称双重锁定
            m = pd.merge(dt, d5, on=['代码','名称']).merge(d10, on=['代码','名称'])
            res = run_sniffer_audit(m, mode="stock")
            st.table(res[['名称', '代码', 'Ea', 'Sm', '审计状态']])
            
            # 爆发点提醒
            targets = res[res['审计状态'] == "💎 爆发点确认"]['名称'].tolist()
            if targets:
                st.success(f"🎯 潜伏目标已锁定：{', '.join(targets)}")
                st.warning("⚠️ Finally: 请进入交易软件确认 15 分钟 K 线缩量上涨形态！")
        except Exception as e:
            st.error("合并失败。请确保三个框粘贴的是同一板块的数据清单。")
