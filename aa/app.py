import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime

# =================== 1. 动态协议穿透引擎 ===================

def protocol_penetrator_sector_scanner():
    """第一步：全网扫描资金流向最强的板块"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "50", "po": "1", "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2+f:!50",
        "fields": "f12,f14,f3,f62,f184"
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        df = pd.DataFrame(resp.json()['data']['diff']).rename(columns={
            'f12': '代码', 'f14': '板块名称', 'f3': '涨跌幅', 'f62': '主力净额', 'f184': '主力占比'
        })
        df['主力净额'] = pd.to_numeric(df['主力净额'], errors='coerce').fillna(0)
        return df
    except: return None

def protocol_penetrator_stock_flow(dynamic_sector_id):
    """第二步：根据扫描到的板块ID，穿透获取个股资金流"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "80", "po": "1", "np": "1",
        "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
        "fltt": "2", "invt": "2", "fid": "f164", 
        "fs": f"b:{dynamic_sector_id}",
        "fields": "f12,f14,f2,f3,f62,f164,f174" 
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        df = pd.DataFrame(resp.json()['data']['diff']).rename(columns={
            'f12': '代码', 'f14': '名称', 'f2': '价格', 'f3': '今日涨幅',
            'f62': '今日主力', 'f164': '5日主力', 'f174': '10日主力'
        })
        for c in ['今日主力', '5日主力', '10日主力']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0) / 10000
        return df
    except: return None

# =================== 2. 扫货痕迹审计核心 ===================

class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return [datetime.now().strftime("%Y%m%d")]

    def analyze_silent_trace(self, df_tick):
        """静默扫货算法：识别高频中性盘与低波动价差"""
        if df_tick is None or df_tick.empty: return 0
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        
        neutral_df = df_tick[df_tick['type'] == '中性']
        n_ratio = len(neutral_df) / len(df_tick) if len(df_tick) > 0 else 0
        p_std = df_tick['price'].std()
        
        score = 0
        if n_ratio > 0.40: score += 2  # 核心特征1：中性盘掩护
        if p_std < 0.005: score += 2   # 核心特征2：价格纹丝不动
        small_amt_ratio = len(neutral_df[neutral_df['成交额'] < 30000]) / len(neutral_df) if len(neutral_df) > 0 else 0
        if small_amt_ratio > 0.8: score += 1 # 核心特征3：算法碎单
        return score

# =================== 3. UI 展现与导入/导出逻辑 ===================

st.set_page_config(page_title="Sniffer Pro V9.8", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro V9.8 - 终极静默扫货审计")

# --- 侧边栏：历史数据导入 ---
st.sidebar.header("📂 报告同步")
uploaded_file = st.sidebar.file_uploader("导入历史审计报告 (CSV)", type="csv")
history_codes = []
if uploaded_file:
    df_hist = pd.read_csv(uploaded_file)
    history_codes = df_hist['代码'].astype(str).str.zfill(6).tolist()
    st.sidebar.success(f"已加载 {len(history_codes)} 个历史监控标的")

# --- Step 1: 全网动态扫描 ---
st.header("Step 1: 全网资金流向扫描")
df_scan = protocol_penetrator_sector_scanner()

if df_scan is not None:
    sector_map = df_scan.set_index('板块名称')['代码'].to_dict()
    st.dataframe(df_scan, use_container_width=True, column_config={
        "主力净额": st.column_config.NumberColumn(format="¥%d"),
        "涨跌幅": st.column_config.NumberColumn(format="%.2f%%")
    })
    
    # --- Step 2: 动态注入与穿透 ---
    st.divider()
    st.header("Step 2: 动态板块穿透")
    target_sector = st.selectbox("选择目标板块审计:", ["请选择"] + list(sector_map.keys()))
    
    if target_sector != "请选择":
        sid = sector_map[target_sector]
        df_stocks = protocol_penetrator_stock_flow(sid)
        
        if df_stocks is not None:
            # 标记逻辑：5日主力流入且涨幅控制
            df_stocks['启动状态'] = np.where(
                (df_stocks['5日主力'] > 500) & (df_stocks['今日涨幅'] < 1.5), 
                "💎 静默扫货", "波段运行"
            )
            # 如果是历史报告中的品种，额外标记
            df_stocks['历史记录'] = df_stocks['代码'].apply(lambda x: "🚩 已在监控" if x in history_codes else "-")
            
            st.dataframe(df_stocks, use_container_width=True, column_config={
                "5日主力": st.column_config.ProgressColumn(min_value=-500, max_value=5000),
                "今日涨幅": st.column_config.NumberColumn(format="%.2f%%")
            })

            # --- Step 3: 深度审计矩阵 ---
            st.divider()
            st.header("Step 3: 三日扫货痕迹审计 (Tick 穿透)")
            default_audit = df_stocks[df_stocks['启动状态'] == "💎 静默扫货"]['名称'].tolist()[:5]
            targets = st.multiselect("勾选审计标的:", df_stocks['名称'].tolist(), default=default_audit)
            
            if targets:
                reports = []
                p_bar = st.progress(0)
                selected_df = df_stocks[df_stocks['名称'].isin(targets)]
                
                for idx, row in selected_df.iterrows():
                    c_str = str(row['代码']).zfill(6)
                    f_code = f"{'sh' if c_str.startswith('6') else 'sz'}{c_str}"
                    
                    report_row = {
                        "名称": row['名称'], "代码": c_str, "状态": row['启动状态'],
                        "5日主力(万)": row['5日主力'], "今日涨幅": row['今日涨幅']
                    }
                    
                    total_s = 0
                    for i, date in enumerate(dates):
                        try:
                            # 穿透网易 Tick 接口获取底层数据
                            df_t = ak.stock_zh_a_tick_163(symbol=f_code, date=date)
                            s = sniffer.analyze_silent_trace(df_t)
                        except: s = 0
                        report_row[f"T-{i}({date})"] = s
                        total_s += s
                    
                    report_row["综合扫货强度"] = total_s
                    reports.append(report_row)
                    p_bar.progress((idx + 1) / len(selected_df))
                
                df_rep = pd.DataFrame(reports)
                st.data_editor(df_rep, use_container_width=True, hide_index=True)
                
                # 最终导出按钮
                st.download_button(
                    label="📥 导出审计报告",
                    data=df_rep.to_csv(index=False).encode('utf_8_sig'),
                    file_name=f"Audit_{target_sector}_{datetime.now().strftime('%m%d')}.csv",
                    mime='text/csv'
                )
