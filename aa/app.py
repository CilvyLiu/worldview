import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# =================== Streamlit 页面配置 ===================
st.set_page_config(page_title="Sniffer 综合 Pro", layout="wide")
st.title("🚀 Sniffer 综合版 - V2/V3 实时嗅探系统")
st.info("💡 模式说明：V2 适合针对性参数审计；V3 适合全盘自动化捕捉‘反波动’异常个股。")

# ----------------- Sidebar 模式与公共配置 -----------------
st.sidebar.header("🛠️ 嗅探控制中心")
mode = st.sidebar.selectbox("选择审计逻辑", ["V2 全盘因子倒查", "V3 投行级自适应审计"])

# ----------------- 公共核心函数 -----------------
def fetch_tick(code):
    """获取并清洗 Tick 数据"""
    try:
        f_code = f"sh{code}" if code.startswith('6') else f"sz{code}"
        # 频率保护
        time.sleep(1.2)
        df_tick = ak.stock_zh_a_tick_163(symbol=f_code)
        if df_tick is None or df_tick.empty:
            return None
        
        # 预处理：时间转换与竞价排除
        df_tick['time_dt'] = pd.to_datetime(df_tick['time'], format='%H:%M:%S', errors='coerce')
        df_tick = df_tick[~((df_tick['time_dt'].dt.hour == 9) & (df_tick['time_dt'].dt.minute < 30))]
        return df_tick
    except:
        return None

def get_sector_stocks(s_name):
    """获取板块成分股"""
    try:
        return ak.stock_board_industry_cons_em(symbol=s_name).head(10)
    except:
        return pd.DataFrame()

# ================== V2 核心逻辑：静态因子评分 ==================
def run_v2():
    st.sidebar.subheader("V2 静态参数调节")
    min_neutral = st.sidebar.slider("中性盘占比阈值", 0.1, 0.5, 0.25)
    interval_limit = st.sidebar.slider("算法频率稳度(std)", 0.5, 5.0, 2.0)
    price_limit = st.sidebar.slider("价格标准差上限", 0.005, 0.05, 0.025)
    vwap_limit = st.sidebar.slider("VWAP偏离度上限", 0.001, 0.02, 0.005)
    
    audited_codes = set()
    results = []

    # 探测板块
    sectors = ak.stock_sector_fund_flow_rank(indicator="今日").head(8)
    if sectors.empty:
        st.warning("未探测到静默流入板块"); return
    
    st.write(f"🔍 正在穿透板块: {', '.join(sectors['名称'].tolist())}")
    
    # 汇总待审个股
    target_list = []
    for _, s_row in sectors.iterrows():
        stocks = get_sector_stocks(s_row['名称'])
        for _, st_row in stocks.iterrows():
            target_list.append((st_row['代码'], st_row['名称'], s_row['名称']))

    progress = st.progress(0)
    status = st.empty()
    
    for i, (code, name, s_name) in enumerate(target_list):
        if code in audited_codes: continue
        audited_codes.add(code)
        
        status.text(f"审计中: {name} ({code})...")
        df_tick = fetch_tick(code)
        
        if df_tick is None or len(df_tick) < 30: continue
        
        # 采样最近 60 笔
        sample = df_tick.tail(60)
        intervals = sample['time_dt'].diff().dt.total_seconds().dropna()
        i_std = intervals.std()
        p_std = sample['price'].std()
        vwap = (sample['price'] * sample['成交额']).sum() / sample['成交额'].sum()
        v_dev = abs(sample['price'].iloc[-1] - vwap) / vwap
        n_ratio = len(sample[sample['type'] == '中性']) / len(sample)
        avg_amt = sample['成交额'].mean()
        b_count = len(sample[sample['成交额'] > max(avg_amt * 5, 100000)])

        # 评分计算
        score = sum([
            i_std < interval_limit, 
            p_std < price_limit, 
            v_dev < vwap_limit, 
            n_ratio > min_neutral, 
            b_count < 6
        ])
        
        results.append({
            "评分": score,
            "代码": code,
            "名称": name,
            "板块": s_name,
            "中性占比": f"{n_ratio*100:.1f}%",
            "频率Std": round(i_std, 2),
            "VWAP偏离": f"{v_dev*100:.3f}%"
        })
        progress.progress((i + 1) / len(target_list))

    if results:
        df_res = pd.DataFrame(results).sort_values(by="评分", ascending=False)
        st.dataframe(df_res.style.highlight_max(axis=0, subset=['评分'], color='#90ee90'), use_container_width=True)
        st.success(f"审计完成！高分标的(4+)共: {len(df_res[df_res['评分']>=4])}")

# ================== V3 核心逻辑：自适应波动对冲 ==================
def run_v3():
    st.sidebar.info("V3 投行模式：系统将自动对标【板块波动基准】。")
    results = []

    try:
        sector_data = ak.stock_sector_fund_flow_rank(indicator="今日").head(6)
    except:
        st.error("无法获取实时板块数据"); return

    progress = st.progress(0)
    status = st.empty()
    
    for idx, s_row in sector_data.iterrows():
        s_name = s_row['名称']
        status.text(f"正在分析板块自适应基准: {s_name}...")
        stocks = get_sector_stocks(s_name)
        if stocks.empty: continue
        
        # 获取板块涨跌幅标准差作为波动基准
        sector_std = stocks['涨跌幅'].std() + 1e-6
        
        for _, st_row in stocks.iterrows():
            df_tick = fetch_tick(st_row['代码'])
            if df_tick is None or len(df_tick) < 30: continue
            
            sample = df_tick.tail(60)
            p_std = sample['price'].std()
            i_std = sample['time_dt'].diff().dt.total_seconds().dropna().std()
            
            # 投行判定逻辑：寻找显著低于板块波动的“死寂”个股
            # 评分因子：1.波动比极低 2.频率稳 3.无暴力抛单
            v_ratio = p_std / sector_std
            score = 0
            if v_ratio < 0.3: score += 1      # 极其受控
            if i_std < 2.5: score += 1        # 机械心跳
            if len(sample[sample['成交额'] > 150000]) < 5: score += 1 # 拆单审计
            
            results.append({
                "评分": score,
                "名称": st_row['名称'],
                "代码": st_row['代码'],
                "波动/板块比": round(v_ratio, 3),
                "个股Std": round(p_std, 3),
                "板块基准Std": round(sector_std, 3),
                "所属板块": s_name
            })
        progress.progress((idx + 1) / len(sector_data))

    if results:
        df_res = pd.DataFrame(results).sort_values(by="评分", ascending=False)
        st.subheader("🏛️ 投行级自适应审计结果")
        st.dataframe(df_res, use_container_width=True)
        st.success(f"发现异常受控标的 (评分2+): {len(df_res[df_res['评分']>=2])}")

# ================== 启动入口 ==================
if st.button("🔥 开始嗅探分析"):
    if "V2" in mode:
        run_v2()
    else:
        run_v3()
