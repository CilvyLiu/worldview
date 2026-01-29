import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import random
from datetime import datetime

# =================== 1. 协议穿透引擎 (Nova 专属：强化抗封锁版) ===================

class RobustConnector:
    """具备自动重试与指纹伪装的连接器"""
    def __init__(self):
        self.session = requests.Session()
        # 配置重试策略：针对连接断开自动重试 3 次
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
    def get_headers(self):
        versions = ["120.0.0.0", "121.0.0.0", "122.0.0.0"]
        return {
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(versions)} Safari/537.36",
            "Referer": "https://data.eastmoney.com/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Connection": "keep-alive"
        }

    def fetch(self, url, params):
        try:
            # 模拟人工随机延迟，防止触发频率封锁
            time.sleep(random.uniform(0.2, 0.5))
            resp = self.session.get(url, params=params, headers=self.get_headers(), timeout=10)
            return resp.json()
        except Exception as e:
            # 即使报错也保持静默，尝试返回空数据由业务层处理
            return None

# 初始化
connector = RobustConnector()

def get_market_sectors_dynamic():
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2+f:!50", 
        "fields": "f12,f14,f3,f62,f184"
    }
    data = connector.fetch(url, params)
    if data and 'data' in data:
        df = pd.DataFrame(data['data']['diff']).rename(columns={
            'f12': 'ID', 'f14': '板块名称', 'f3': '今日涨幅', 
            'f62': '主力净额', 'f184': '主力占比'
        })
        df['板块评分'] = pd.to_numeric(df['主力净额'], errors='coerce') / 100000000
        return df.sort_values(by='板块评分', ascending=False)
    return None

def get_stock_penetration(sector_id):
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
        "fltt": "2", "invt": "2", "fid": "f164", 
        "fs": f"b:{sector_id}",
        "fields": "f12,f14,f2,f3,f62,f164,f174" 
    }
    data = connector.fetch(url, params)
    if data and 'data' in data:
        df = pd.DataFrame(data['data']['diff']).rename(columns={
            'f12': '代码', 'f14': '名称', 'f2': '价格', 'f3': '今日涨幅',
            'f62': '今日主力', 'f164': '5日主力', 'f174': '10日主力'
        })
        for c in ['今日主力', '5日主力', '10日主力']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0) / 10000
        return df
    return None

# =================== 2. 扫货痕迹审计 (Nova 核心算法) ===================

class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return [datetime.now().strftime("%Y%m%d")]

    def analyze_silent_trace(self, df_tick):
        if df_tick is None or df_tick.empty: return 0
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        n_df = df_tick[df_tick['type'] == '中性']
        n_ratio = len(n_df) / len(df_tick) if len(df_tick) > 0 else 0
        score = 0
        if n_ratio > 0.40: score += 2 
        if df_tick['price'].std() < 0.005: score += 2  
        return score

# =================== 3. 动态侦测 UI ===================

st.set_page_config(page_title="Sniffer Pro V12.0", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro V12.0 - 稳健级侦测系统")
st.caption(f"当前用户: Nova | 协议层: Retry-Persistence Mode 已开启")

# --- Step 1 ---
st.header("Step 1: 全市场板块资金侦测")
df_all = get_market_sectors_dynamic()

if df_all is not None:
    st.sidebar.info(f"审计范围: {', '.join(dates)}")
    st.dataframe(df_all, use_container_width=True)
    
    st.divider()
    s_map = df_all.set_index('板块名称')['ID'].to_dict()
    target_sec = st.selectbox("🎯 选定待审计板块:", ["请选择探测目标"] + list(s_map.keys()))

    if target_sec != "请选择探测目标":
        sid = s_map[target_sec]
        # --- Step 2 ---
        st.header(f"Step 2: {target_sec} - 个股侦测")
        df_s = get_stock_penetration(sid)
        if df_s is not None:
            df_s['侦测状态'] = np.where((df_s['5日主力'] > 500) & (df_s['今日涨幅'] < 1.5), "💎 静默扫货", "正常波动")
            st.dataframe(df_s, use_container_width=True)

            # --- Step 3 ---
            st.divider()
            st.header("Step 3: 三日深度审计")
            targets = st.multiselect("勾选标的:", df_s['名称'].tolist(), 
                                     default=df_s[df_s['侦测状态']=="💎 静默扫货"]['名称'].tolist()[:3])
            
            if targets:
                reports = []
                p_bar = st.progress(0)
                selected = df_s[df_s['名称'].isin(targets)]
                for idx, (s_idx, row) in enumerate(selected.iterrows()):
                    c = str(row['代码']).zfill(6)
                    f = f"{'sh' if c.startswith('6') else 'sz'}{c}"
                    r = {"名称": row['名称'], "代码": c, "今日涨幅%": row['今日涨幅']}
                    ts = 0
                    for d in dates:
                        try:
                            # Tick数据获取通常较稳，但仍建议加异常捕捉
                            d_t = ak.stock_zh_a_tick_163(symbol=f, date=d)
                            s = sniffer.analyze_silent_trace(d_t)
                        except: s = 0
                        r[f"{d}审计"] = s
                        ts += s
                    r["总得分"] = ts
                    reports.append(r)
                    p_bar.progress((idx + 1) / len(selected))
                
                st.dataframe(pd.DataFrame(reports).style.background_gradient(subset=['总得分'], cmap='YlGn'), use_container_width=True)
                st.download_button("📥 导出最终报告", pd.DataFrame(reports).to_csv(index=False).encode('utf_8_sig'), "Audit.csv")
