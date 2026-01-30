import streamlit as st
import pandas as pd
import numpy as np
import io

# =================== 1. 数据清洗引擎 (智能识别东财板块个股清单) ===================

def to_num(s):
    """智能识别数值，处理 %, 万, 亿"""
    if pd.isna(s):
        return 0.0
    s = str(s).replace(',', '').replace('%', '').strip()
    if '亿' in s:
        try: return float(s.replace('亿', '')) * 1e8
        except: return 0.0
    if '万' in s:
        try: return float(s.replace('万', '')) * 1e4
        except: return 0.0
    try:
        return float(s)
    except:
        return 0.0

def find_percent_col(df):
    """寻找含%列 (通常为今日主力占比)"""
    for col in df.columns:
        try:
            if df[col].astype(str).str.contains('%').mean() > 0.4:
                return col
        except:
            continue
    return None

def clean_em_data(raw_text, mode="sector"):
    """
    清洗逻辑：
    板块：名称(1), 涨幅(4), 占比(智能搜索%)
    个股清单：代码(1), 名称(2), 主力净额(6)
    """
    try:
        # 自动识别分隔符（空格或Tab）
        df = pd.read_csv(io.StringIO(raw_text), sep=r'\s+', header=None, on_bad_lines='skip')
        
        if mode == "sector":
            processed = pd.DataFrame()
            processed['名称'] = df.iloc[:, 1]
            processed['今日涨幅'] = df.iloc[:, 4].apply(to_num)
            pct_col = find_percent_col(df)
            processed['主力占比'] = df[pct_col].apply(to_num) if pct_col is not None else 0.0
            return processed.dropna(subset=['名称'])
        else:
            # 适配板块内个股详情列表复制
            processed = pd.DataFrame()
            processed['代码'] = df.iloc[:, 1].astype(str)
            processed['名称'] = df.iloc[:, 2]
            processed['主力净额'] = df.iloc[:, 6].apply(to_num)
            return processed.dropna(subset=['名称'])
    except Exception as e:
        return pd.DataFrame()

# =================== 2. 投行算法内核 (禁止删减) ===================

def run_sniffer_audit(df, mode="stock"):
    # 数值强制转换
    cols = [c for c in df.columns if c not in ['名称', '代码', '审计状态']]
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if mode == "sector":
        # First: L-H 扫货区审计 (Nova 逻辑：占比>3%, 涨幅<2%)
        df['审计状态'] = np.where(
            (df['主力占比'] > 3.0) & (df['今日涨幅'] < 2.0), 
            "🚩 重点关注 (L-H扫货区)", 
            "待机"
        )
        return df.sort_values(by='主力占比', ascending=False)
    
    else:
        # Next: 穿透审计 Ea, Sm, Signal
        # 1. Ea 吸筹效率
        df['Ea'] = df['今日主力'] / (10000 * 2.1) 
        # 2. Sm 持仓稳定性 (权重：0.5, 0.3, 0.2)
        df['weighted_sum'] = df['今日主力']*0.5 + df['5日主力']*0.3 + df['10日主力']*0.2
        df['std_flow'] = df.apply(lambda x: np.std([x['今日主力'], x['5日主力'], x['10日主力']]), axis=1)
        df['Sm'] = df['weighted_sum'] / (df['std_flow'] + 1)
        # 3. Signal 爆发点识别
        df['is_target'] = (df['今日主力'] > 0) & (df['5日主力'] < 0) & (df['10日主力'] < 0)
        df['审计状态'] = np.where(df['is_target'], "💎 爆发点确认", "洗盘中")
        return df.sort_values(by='Ea', ascending=False)

# =================== 3. UI 界面 (按钮驱动 & 手机优化) ===================

st.set_page_config(page_title="Sniffer Pro Mobile", layout="wide")
st.title("🏛️ Sniffer 嗅嗅 - 投行数据审计终端")

# Step 1: 板块
st.header("Step 1: First - 板块初筛")
sector_input = st.text_area("📥 粘贴板块一日行情 (含名称、涨幅、主力占比)", height=120)
if st.button("🚀 执行板块审计", use_container_width=True):
    if sector_input:
        sec_res = run_sniffer_audit(clean_em_data(sector_input, mode="sector"), mode="sector")
        if not sec_res.empty:
            st.table(sec_res[['名称', '今日涨幅', '主力占比', '审计状态']])
        else:
            st.error("❌ 板块数据解析失败，请确保复制了完整的行。")

# Step 2: 个股
st.divider()
st.header("Step 2: Next - 个股穿透")
st.caption("进入重点板块，分别粘贴该板块下的【今日/5日/10日】个股清单全行数据")

col1, col2, col3 = st.columns(3)
with col1: in_t = st.text_area("1. 今日个股清单", height=120)
with col2: in_5 = st.text_area("2. 5日个股清单", height=120)
with col3: in_10 = st.text_area("3. 10日个股清单", height=120)

if st.button("🔍 执行个股穿透审计", use_container_width=True):
    if in_t and in_5 and in_10:
        df_t = clean_em_data(in_t, mode="stock").rename(columns={'主力净额':'今日主力'})
        df_5 = clean_em_data(in_5, mode="stock").rename(columns={'主力净额':'5日主力'})
        df_10 = clean_em_data(in_10, mode="stock").rename(columns={'主力净额':'10日主力'})
        
        try:
            # 严格使用代码和名称双重对齐
            m = pd.merge(df_t, df_5, on=['代码','名称'])
            m = pd.merge(m, df_10, on=['代码','名称'])
            
            st_res = run_sniffer_audit(m, mode="stock")
            st.table(st_res[['名称', '代码', 'Ea', 'Sm', '审计状态']])
            
            targets = st_res[st_res['is_target'] == True]['名称'].tolist()
            if targets:
                st.success(f"🎯 爆发点确认：{', '.join(targets)}")
                st.warning("⚠️ Finally: 请确认 15 分钟 K 线缩量上涨！")
        except Exception as e:
            st.error(f"合并失败。请确保三个时间周期粘贴的是同一板块下的清单。")
