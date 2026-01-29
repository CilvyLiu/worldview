import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import requests
import random
import time
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =================== 1. 协议穿透引擎 (Nova 专属：抗封锁双轨版) ===================

class NovaRobustConnector:
    """具备指纹伪装与指数退避重连的顶级连接器"""
    def __init__(self):
        self.session = requests.Session()
        # 定义重试规则：针对物理断开、连接超时自动重试 5 次
        retries = Retry(
            total=5,
            backoff_factor=1,  # 失败后等待时间依次增加 (1s, 2s, 4s...)
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def get_dynamic_headers(self):
        """生成随机浏览器指纹"""
        chrome_ver = f"{random.randint(110, 122)}.0.{random.randint(1000, 6000)}.{random.randint(10, 200)}"
        return {
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver} Safari/537.36",
            "Referer": "https://quote.eastmoney.com/center/boardlist.html",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive"
        }

    def fetch(self, url, params):
        """核心拉取方法：注入随机指纹与防抖延迟"""
        try:
            params['cb'] = f"jQuery{random.randint(1000000, 9999999)}_{int(time.time()*1000)}"
            params['_'] = int(time.time()*1000)
            
            # 关键：模拟人工点击间的微小间隔
            time.sleep(random.uniform(0.3, 0.7))
            
            resp = self.session.get(url, params=params, headers=self.get_dynamic_headers(), timeout=15)
            # 提取 JSON 数据 (处理 jQuery 回调包裹)
            text = resp.text
            if not text or "(" not in text:
                return None
            json_str = text[text.find("(")+1 : text.rfind(")")]
            import json
            return json.loads(json_str)
        except Exception:
            return None

# 全局共用一个 Connector 实例
if 'nova_conn' not in st.session_state:
    st.session_state.nova_conn = NovaRobustConnector()

@st.cache_data(ttl=300) # 5分钟内不再重复请求相同板块，防止封 IP
def get_market_sectors_cached():
    """板块侦测：采用强化版穿透协议"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2+f:!50",
        "fields": "f12,f14,f3,f62,f184"
    }
    data = st.session_state.nova_conn.fetch(url, params)
    if data and 'data' in data and 'diff' in data:
        df = pd.DataFrame(data['data']['diff']).rename(columns={
            'f12': 'ID', 'f14': '板块名称', 'f3': '今日涨幅', 
            'f62': '主力净额', 'f184': '主力占比'
        })
        df['板块评分'] = pd.to_numeric(df['主力净额'], errors='coerce') / 100000000
        return df.sort_values(by='板块评分', ascending=False)
    return None

@st.cache_data(ttl=60) # 1分钟缓存，避免操作下拉框时重复请求个股数据
def get_stock_penetration_cached(sector_id):
    """个股穿透：支持长效 Session 协议"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
        "fltt": "2", "invt": "2", "fid": "f164",
        "fs": f"b:{sector_id}",
        "fields": "f12,f14,f2,f3,f62,f164,f174"
    }
    data = st.session_state.nova_conn.fetch(url, params)
    if data and 'data' in data and 'diff' in data:
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
        p_std = df_tick['price'].std()
        
        score = 0
        if n_ratio > 0.40: score += 2 
        if p_std is not None and p_std < 0.005: score += 2  
        return score

# =================== 3. 动态侦测 UI ===================

st.set_page_config(page_title="Sniffer Pro V12.0", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro V12.0 - 投行级稳健系统")
st.caption(f"Nova 专属模式 | 已激活随机指纹对抗协议")

# --- Step 1 ---
st.header("Step 1: 全市场板块资金侦测")
df_all = get_market_sectors_cached()

if df_all is not None:
    st.dataframe(df_all, use_container_width=True)
    csv_s1 = df_all.to_csv(index=False).encode('utf_8_sig')
    st.download_button("📥 导出板块报告", data=csv_s1, file_name="Sectors.csv")
    
    st.divider()
    s_map = df_all.set_index('板块名称')['ID'].to_dict()
    target_sec = st.selectbox("🎯 选定待审计板块:", ["请选择探测目标"] + list(s_map.keys()))

    if target_sec != "请选择探测目标":
        sid = s_map[target_sec]
        # --- Step 2 ---
        st.header(f"Step 2: {target_sec} - 个股侦测")
        df_s = get_stock_penetration_cached(sid)
        if df_s is not None:
            df_s['侦测状态'] = np.where((df_s['5日主力'] > 500) & (df_s['今日涨幅'] < 1.5), "💎 疑似静默扫货", "正常波动")
            st.dataframe(df_s, use_container_width=True)
            
            # --- Step 3 ---
            st.divider()
            st.header("Step 3: 三日深度复盘")
            targets = st.multiselect("勾选标的:", df_s['名称'].tolist(), 
                                     default=df_s[df_s['侦测状态']=="💎 疑似静默扫货"]['名称'].tolist()[:2])
            
            if targets:
                if st.button("🔍 开始执行 Tick 审计 (Nova 算法)"):
                    reports = []
                    p_bar = st.progress(0)
                    selected = df_s[df_s['名称'].isin(targets)]
                    for idx, (s_idx, row) in enumerate(selected.iterrows()):
                        c = str(row['代码']).zfill(6)
                        f = f"{'sh' if c.startswith('6') else 'sz'}{c}"
                        r = {"名称": row['名称'], "审计得分": 0}
                        ts = 0
                        for d in dates:
                            try:
                                d_t = ak.stock_zh_a_tick_163(symbol=f, date=d)
                                s = sniffer.analyze_silent_trace(d_t)
                            except: s = 0
                            ts += s
                        r["审计得分"] = ts
                        reports.append(r)
                        p_bar.progress((idx + 1) / len(selected))
                    
                    st.table(pd.DataFrame(reports))
                    st.download_button("📥 导出报告", pd.DataFrame(reports).to_csv(index=False).encode('utf_8_sig'), "Audit.csv")
else:
    st.info("🔄 正在绕过防火墙，请点击右侧侧边栏 'Clear Cache' 或稍后再试。")
