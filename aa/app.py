import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime
import requests

# =================== 1. 协议穿透引擎 (板块 & 个股资金流) ===================
def protocol_penetrator_sector(period="今日"):
    """穿透获取板块排行"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    mapping = {
        "今日": {"fid": "f62", "fields": "f12,f14,f2,f3,f62,f184"},
        "5日": {"fid": "f164", "fields": "f12,f14,f2,f109,f164,f165"},
        "10日": {"fid": "f174", "fields": "f12,f14,f2,f160,f174,f175"}
    }
    cfg = mapping.get(period, mapping["今日"])
    params = {
        "pn": "1", "pz": "50", "po": "1", "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": "2", "invt": "2", "fid": cfg["fid"],
        "fs": "m:90+t:2+f:!50", "fields": cfg["fields"]
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        df = pd.DataFrame(resp.json()['data']['diff'])
        rename_map = {'f12': '代码', 'f14': '名称'}
        if period == "今日": rename_map.update({'f3': '涨跌幅', 'f62': '主力净流入-净额', 'f184': '占比'})
        elif period == "5日": rename_map.update({'f109': '涨跌幅', 'f164': '主力净流入-净额', 'f165': '占比'})
        else: rename_map.update({'f160': '涨跌幅', 'f174': '主力净流入-净额', 'f175': '占比'})
        return df.rename(columns=rename_map)
    except: return None

def protocol_penetrator_stocks_in_sector(sector_id):
    """
    【核心修改】使用 Nova 提供的个股资金流接口
    穿透获取板块内个股的 5日/10日 净额
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "80", "po": "1", "np": "1",
        "ut": "8dec03ba335b81bf4ebdf7b29ec27d15", # Nova 提供的 Token
        "fltt": "2", "invt": "2", "fid": "f164", # 默认按 5日主力净额排序
        "fs": f"b:{sector_id}",
        "fields": "f12,f14,f2,f3,f62,f164,f174" # 获取多周期净额
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        df = pd.DataFrame(resp.json()['data']['diff']).rename(columns={
            'f12': '代码', 'f14': '名称', 'f2': '价格', 'f3': '涨幅',
            'f62': '今日主力', 'f164': '5日主力', 'f174': '10日主力'
        })
        # 换算单位为万元
        for c in ['今日主力', '5日主力', '10日主力']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0) / 10000
        return df
    except: return None

# =================== 2. 审计核心类 ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return []

    def anti_iceberg_audit(self, df_tick):
        if df_tick is None or df_tick.empty: return 0
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        neutral_df = df_tick[df_tick['type'] == '中性']
        n_ratio = len(neutral_df) / len(df_tick) if len(df_tick) > 0 else 0
        p_std = df_tick['price'].std()
        score = 0
        if n_ratio > 0.35: score += 2
        if p_std is not None and p_std < 0.008: score += 2
        if len(neutral_df) > 0 and (len(neutral_df[neutral_df['成交额'] < 50000]) > len(neutral_df)*0.7): score += 1
        return int(score)

# =================== 3. UI 交互层 ===================
st.set_page_config(page_title="Sniffer Pro V8.9.8", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)
labels = ["本日", "昨日", "前日"]

st.title("🏛️ Sniffer Pro V8.9.8 - 资金流审计全穿透")

# Step 1: 板块快照
period = st.sidebar.selectbox("板块统计周期", ["今日", "5日", "10日"])
st.header(f"Step 1: {period}板块行情监视")
df_sec = protocol_penetrator_sector(period=period)

if df_sec is not None:
    st.dataframe(df_sec[['名称', '代码', '涨跌幅', '主力净流入-净额']], use_container_width=True)
    sector_map = df_sec.set_index('名称')['代码'].to_dict()
    
    # Step 2: 个股深挖
    st.divider()
    st.header("Step 2: 目标板块个股资金穿透")
    selected_sec = st.selectbox("选择审计板块:", ["请选择"] + list(sector_map.keys()))
    
    if selected_sec != "请选择":
        sid = sector_map[selected_sec]
        df_stocks = protocol_penetrator_stocks_in_sector(sid)
        
        if df_stocks is not None:
            st.subheader(f"📍 {selected_sec} ({sid}) 个股资金面 (万元)")
            st.dataframe(df_stocks.style.background_gradient(cmap='RdYlGn', subset=['今日主力', '5日主力', '10日主力']), use_container_width=True)
            
            # Step 3: 三日数字审计
            st.divider()
            st.header("Step 3: 算法控盘评分矩阵")
            selected_names = st.multiselect("选取审计对象:", df_stocks['名称'].tolist(), default=df_stocks['名称'].tolist()[:5])
            
            if selected_names:
                reports = []
                p_bar = st.progress(0)
                target_df = df_stocks[df_stocks['名称'].isin(selected_names)]
                
                for idx, row in target_df.iterrows():
                    code_str = str(row['代码']).zfill(6)
                    f_code = f"{'sh' if code_str.startswith('6') else 'sz'}{code_str}"
                    audit_row = {
                        "名称": row['名称'], "代码": code_str,
                        "5日净额": round(row['5日主力'], 2), "10日净额": round(row['10日主力'], 2)
                    }
                    for i, date in enumerate(dates):
                        try:
                            df_t = ak.stock_zh_a_tick_163(symbol=f_code, date=date)
                            audit_row[f"T-{i}({labels[i]})"] = sniffer.anti_iceberg_audit(df_t)
                        except: audit_row[f"T-{i}({labels[i]})"] = 0
                    reports.append(audit_row)
                    p_bar.progress((idx + 1) / len(selected_names))
                
                df_rep = pd.DataFrame(reports)
                st.dataframe(df_rep.style.background_gradient(cmap='Greens', subset=[c for c in df_rep.columns if "T-" in c]), use_container_width=True)
                
                st.download_button("📥 导出综合报表", df_rep.to_csv(index=False).encode('utf_8_sig'), f"Audit_{sid}.csv")
