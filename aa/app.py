import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# =================== 1. 强力数据清洗引擎 ===================

def to_num(s):
    """极致兼容：处理千分位、负号、百分号、单位、以及长浮点数"""
    if pd.isna(s): return 0.0
    s = str(s).strip()
    # 移除逗号（千分位）
    s = s.replace(',', '')
    # 提取数字、负号和小数点
    match = re.search(r'[-+]?\d*\.?\d+', s)
    if not match: return 0.0
    
    val = float(match.group())
    if '%' in s: val = val # 占比通常直接用数值比较
    if '亿' in s: val *= 1e8
    if '万' in s: val *= 1e4
    return val

def clean_em_data(raw_text, mode="sector"):
    try:
        # 使用正则表达式处理不规则空格/Tab
        lines = [line.strip() for line in raw_text.strip().split('\n') if line.strip()]
        data = [re.split(r'\s+', line) for line in lines]
        df = pd.DataFrame(data)
        
        if mode == "sector":
            # 自动探测逻辑：名称通常是第一个非数字字符串
            processed = pd.DataFrame()
            # 遍历每一行，寻找第一个包含中文的列作为名称
            def find_name(row):
                for item in row:
                    if re.search(r'[\u4e00-\u9fa5]', str(item)): return item
                return "未知"
            
            processed['名称'] = df.apply(find_name, axis=1)
            # 针对你刚才贴出的格式：涨幅通常紧随名称，占比在后面
            # 采用更稳妥的办法：取所有能转成数字的列
            num_df = df.apply(lambda x: x.apply(to_num))
            
            # 逻辑：涨幅通常在 [ -20, 20 ] 之间，占比通常也在这个区间或更大
            # 我们直接锁定你给的格式偏移量
            processed['今日涨幅'] = df.iloc[:, 4].apply(to_num) if df.shape[1] > 4 else 0.0
            processed['主力占比'] = df.iloc[:, 12].apply(to_num) if df.shape[1] > 12 else df.iloc[:, -1].apply(to_num)
            
            return processed[processed['名称'] != "未知"]
        else:
            # 个股逻辑：名称(2), 主力净额(6)
            processed = pd.DataFrame()
            processed['代码'] = df.iloc[:, 1].astype(str)
            processed['名称'] = df.iloc[:, 2]
            processed['主力净额'] = df.iloc[:, 6].apply(to_num)
            return processed.dropna(subset=['名称'])
    except:
        return pd.DataFrame()

# =================== 2. 算法与 UI (保持 Nova 核心指令) ===================

def run_sniffer_audit(df, mode="stock"):
    for col in [c for c in df.columns if c not in ['名称', '代码']]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if mode == "sector":
        df['审计状态'] = np.where((df['主力占比'] > 3.0) & (df['今日涨幅'] < 2.0), "🚩 重点关注", "待机")
        return df.sort_values(by='主力占比', ascending=False)
    else:
        df['Ea'] = df['今日主力'] / (10000 * 2.1)
        df['weighted_sum'] = df['今日主力']*0.5 + df['5日主力']*0.3 + df['10日主力']*0.2
        df['std_flow'] = df.apply(lambda x: np.std([x['今日主力'], x['5日主力'], x['10日主力']]), axis=1)
        df['Sm'] = df['weighted_sum'] / (df['std_flow'] + 1)
        df['is_target'] = (df['今日主力'] > 0) & (df['5日主力'] < 0) & (df['10日主力'] < 0)
        df['审计状态'] = np.where(df['is_target'], "💎 爆发点确认", "洗盘中")
        return df.sort_values(by='Ea', ascending=False)

st.set_page_config(page_title="Sniffer Pro", layout="wide")
st.title("🏛️ Sniffer 嗅嗅 - 投行审计终端")

# Step 1
st.header("Step 1: First")
sector_input = st.text_area("📥 粘贴板块数据", height=120)
if st.button("🚀 执行板块审计", use_container_width=True):
    if sector_input:
        res = run_sniffer_audit(clean_em_data(sector_input, mode="sector"), mode="sector")
        st.table(res[['名称', '今日涨幅', '主力占比', '审计状态']])

# Step 2
st.divider()
st.header("Step 2: Next")
c1, c2, c3 = st.columns(3)
with c1: in_t = st.text_area("1. 今日", height=120)
with c2: in_5 = st.text_area("2. 5日", height=120)
with c3: in_10 = st.text_area("3. 10日", height=120)

if st.button("🔍 执行个股穿透", use_container_width=True):
    if in_t and in_5 and in_10:
        dt = clean_em_data(in_t, mode="stock").rename(columns={'主力净额':'今日主力'})
        d5 = clean_em_data(in_5, mode="stock").rename(columns={'主力净额':'5日主力'})
        d10 = clean_em_data(in_10, mode="stock").rename(columns={'主力净额':'10日主力'})
        try:
            m = pd.merge(dt, d5, on=['代码','名称']).merge(d10, on=['代码','名称'])
            res = run_sniffer_audit(m, mode="stock")
            st.table(res[['名称', '代码', 'Ea', 'Sm', '审计状态']])
        except: st.error("合并失败，请检查数据清单是否匹配。")
