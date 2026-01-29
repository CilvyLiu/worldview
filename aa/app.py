import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime
import plotly.graph_objects as go
import requests
import json

# =================== 1. 协议穿透引擎 (核心：板块+个股) ===================
def protocol_penetrator_sector():
    """穿透东财底层 API 获取板块资金流"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "50", "po": "1", "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2+f:!50",
        "fields": "f12,f14,f2,f3,f62,f184"
    }
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0", "Referer": "https://data.eastmoney.com/"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()['data']['diff']
        df = pd.DataFrame(data).rename(columns={
            'f14': '名称', 'f12': '代码', 'f3': '今日涨跌幅', 
            'f62': '主力净流入-净额', 'f184': '主力净流入-净占比'
        })
        # 统一清洗
        for c in ['今日涨跌幅', '主力净流入-净占比']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except:
        return None

def robust_request(func, *args, **kwargs):
    """通用请求熔断器"""
    for i in range(3):
        try:
            time.sleep(random.uniform(1.0, 2.0))
            res = func(*args, **kwargs)
            if res is not None and not (isinstance(res, pd.DataFrame) and res.empty):
                return res
        except: continue
    return None

# =================== 2. 审计核心类 ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return []

    def anti_iceberg_audit(self, df_tick):
        if df_tick is None or df_tick.empty: return 0, "缺失"
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        neutral_df = df_tick[df_tick['type'] == '中性']
        total_len = len(df_tick)
        n_ratio = len(neutral_df) / total_len if total_len > 0 else 0
        p_std = df_tick['price'].std()
        small_neutral = len(neutral_df[neutral_df['成交额'] < 50000])
        
        score = 0
        if n_ratio > 0.35: score += 2
        if p_std is not None and p_std < 0.008: score += 2
        if len(neutral_df) > 0 and small_neutral > len(neutral_df) * 0.7: score += 1
        return score, ("极高" if score >= 4 else "弱")

# =================== 3. UI 交互层 ===================
st.set_page_config(page_title="Sniffer Pro V8.9", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)
labels = ["本日", "昨日", "前日"]

st.title("🏛️ Sniffer Pro V8.9 - 穿透导出终极版")

# 侧边栏：状态监控
st.sidebar.header("📡 实时流监测")
st.sidebar.metric("数据源脉搏", datetime.now().strftime('%H:%M:%S'))
for i, d in enumerate(dates):
    st.sidebar.write(f"T-{i}: {d}")

# --- Step 1: 板块穿透 ---
st.header("Step 1: 捕捉【协议穿透】异常板块")
# 穿透优先逻辑
df_sectors = protocol_penetrator_sector()
if df_sectors is None:
    st.warning("⚠️ 协议穿透失败，尝试 Akshare 备份...")
    df_sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")

if df_sectors is not None:
    # 自动定标
    target_sectors = df_sectors[(df_sectors['今日涨跌幅'] > 0.5) & (df_sectors['今日涨跌幅'] < 4.0)]
    if target_sectors.empty:
        target_sectors = df_sectors.sort_values('主力净流入-净占比', ascending=False).head(10)
    
    col1, col2 = st.columns([4, 1])
    with col1: st.dataframe(target_sectors, use_container_width=True)
    with col2: 
        st.download_button("📥 导出板块报告", target_sectors.to_csv(index=False).encode('utf_8_sig'), 
                           "Sector_Report.csv", "text/csv")
else:
    st.error("🔴 无法握手数据源，请检查 IP。")
    st.stop()

# --- Step 2: 个股穿透 ---
st.divider()
st.header("Step 2: 穿透精选个股 (反过热筛选)")
selected_sector = st.selectbox("选择审计板块:", ["请选择"] + target_sectors['名称'].tolist())

if selected_sector != "请选择":
    all_stocks = robust_request(ak.stock_board_industry_cons_em, symbol=selected_sector)
    if all_stocks is not None:
        all_stocks['涨跌幅'] = pd.to_numeric(all_stocks['涨跌幅'], errors='coerce').fillna(0)
        quality_stocks = all_stocks[(all_stocks['涨跌幅'] < 5.0) & (all_stocks['换手率'] < 10.0)].head(15)
        
        st.subheader(f"📍 {selected_sector} 审计池")
        selected_stocks = st.multiselect("选取审计标的：", quality_stocks['名称'].tolist(), default=quality_stocks['名称'].tolist()[:3])
        
        # --- Step 3: 审计执行 ---
        if selected_stocks:
            st.divider()
            st.header("Step 3: 三日跨时序【反冰山审计】")
            codes = quality_stocks[quality_stocks['名称'].isin(selected_stocks)]['代码'].tolist()
            name_map = quality_stocks.set_index('代码')['名称'].to_dict()
            
            # 执行批量 Tick 审计
            reports = []
            p_bar = st.progress(0)
            for idx, code in enumerate(codes):
                code_str = str(code).zfill(6)
                f_code = f"{'sh' if code_str.startswith('6') else 'sz'}{code_str}"
                row = {"名称": name_map.get(code), "代码": code_str}
                for i, date in enumerate(dates):
                    df_t = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
                    score, _ = sniffer.anti_iceberg_audit(df_t)
                    row[f"T-{i}评分"] = score
                reports.append(row)
                p_bar.progress((idx + 1) / len(codes))
            
            df_rep = pd.DataFrame(reports)
            score_cols = [c for c in df_rep.columns if "评分" in c]
            
            col_a, col_b = st.columns([4, 1])
            with col_a: st.dataframe(df_rep.style.background_gradient(cmap='RdYlGn', subset=score_cols), use_container_width=True)
            with col_b: st.download_button("📥 导出审计报告", df_rep.to_csv(index=False).encode('utf_8_sig'), 
                                          "Audit_Report.csv", "text/csv")

            # --- Step 4: 雷达图可视化 ---
            st.divider()
            st.header("Step 4: 算法指纹雷达")
            chart_cols = st.columns(3)
            for i, (_, r) in enumerate(df_rep.iterrows()):
                with chart_cols[i % 3]:
                    fig = go.Figure(data=go.Scatterpolar(r=[r[c] for c in score_cols], theta=labels, fill='toself'))
                    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), title=r['名称'], height=300)
                    st.plotly_chart(fig, use_container_width=True)
