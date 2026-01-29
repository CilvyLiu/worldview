import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime
import requests

# =================== 1. 协议穿透引擎 (Nova 专属) ===================
def protocol_penetrator_stock_flow(sector_id="BK0732"):
    """穿透获取板块内个股 5日/10日 净额"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "80", "po": "1", "np": "1",
        "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
        "fltt": "2", "invt": "2", "fid": "f164", 
        "fs": f"b:{sector_id}",
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

# =================== 2. 增强型审计核心 ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return []

    def anti_iceberg_audit(self, df_tick):
        """核心算法：返回 0-5 整数评分"""
        if df_tick is None or df_tick.empty: return 0
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        neutral_df = df_tick[df_tick['type'] == '中性']
        total_len = len(df_tick)
        n_ratio = len(neutral_df) / total_len if total_len > 0 else 0
        p_std = df_tick['price'].std()
        
        score = 0
        # 痕迹1：中性盘占比极高 (主力在对倒或隐藏单)
        if n_ratio > 0.40: score += 2
        # 痕迹2：价差极小 (静默扫货，不拉升股价)
        if p_std is not None and p_std < 0.005: score += 2
        # 痕迹3：小额密集成交 (程序化算法吸筹)
        small_neutral = len(neutral_df[neutral_df['成交额'] < 30000])
        if len(neutral_df) > 0 and small_neutral > len(neutral_df) * 0.8: score += 1
        return int(score)

# =================== 3. UI 交互层 ===================
st.set_page_config(page_title="Sniffer Pro V9.0", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)
labels = ["本日", "昨日", "前日"]

st.title("🏛️ Sniffer Pro V9.0 - 静默扫货审计系统")

# Step 1: 板块穿透
st.sidebar.header("📡 监控参数")
target_period = st.sidebar.selectbox("统计参考周期", ["今日", "5日", "10日"])
df_sectors = ak.stock_sector_fund_flow_rank(indicator="今日") # 获取实时映射
sector_map = df_sectors.set_index('名称')['代码'].to_dict()

st.header(f"Step 1: 板块穿透监视")
selected_sector = st.selectbox("选择审计板块:", ["请选择"] + list(sector_map.keys()))

if selected_sector != "请选择":
    sid = sector_map[selected_sector]
    df_stocks = protocol_penetrator_stock_flow(sid)
    
    if df_stocks is not None:
        # 自动识别“静默状态”：5日净流入 > 0 且 今日涨幅 < 2%
        df_stocks['痕迹描述'] = np.where(
            (df_stocks['5日主力'] > 0) & (df_stocks['涨幅'] < 2), 
            "⚠️ 静默吸筹中", "正常波段"
        )
        st.dataframe(df_stocks.style.background_gradient(cmap='RdYlGn', subset=['5日主力', '10日主力']), use_container_width=True)

        # Step 2: 审计矩阵
        st.divider()
        st.header("Step 2: 深度审计矩阵 (扫货痕迹分析)")
        selected_names = st.multiselect("勾选审计标的:", df_stocks['名称'].tolist(), default=df_stocks['名称'].tolist()[:8])
        
        if selected_stocks := selected_names:
            reports = []
            p_bar = st.progress(0)
            target_df = df_stocks[df_stocks['名称'].isin(selected_stocks)]
            
            for idx, row in target_df.iterrows():
                code_str = str(row['代码']).zfill(6)
                f_code = f"{'sh' if code_str.startswith('6') else 'sz'}{code_str}"
                
                # 初始化报告行
                audit_row = {
                    "名称": row['名称'], "代码": code_str, "价格": row['价格'],
                    "5日主力(万)": round(row['5日主力'], 2), "当前涨幅": row['涨幅'],
                    "静默状态": row['痕迹描述']
                }
                
                total_score = 0
                for i, date in enumerate(dates):
                    try:
                        # 此处为模拟调用，实际使用 ak.stock_zh_a_tick_163
                        df_t = ak.stock_zh_a_tick_163(symbol=f_code, date=date)
                        day_score = sniffer.anti_iceberg_audit(df_t)
                    except: day_score = 0
                    audit_row[f"T-{i}_{labels[i]}分"] = day_score
                    total_score += day_score
                
                audit_row["综合控盘度"] = total_score
                reports.append(audit_row)
                p_bar.progress((idx + 1) / len(target_df))
            
            df_rep = pd.DataFrame(reports)
            
            # 强化可视化
            st.dataframe(
                df_rep.style.background_gradient(cmap='Oranges', subset=['综合控盘度'])
                .apply(lambda x: ['background: #103010' if v == "⚠️ 静默吸筹中" else '' for v in x], axis=1),
                use_container_width=True
            )
            
            # Step 3: 导出综合报告
            st.divider()
            csv_data = df_rep.to_csv(index=False).encode('utf_8_sig')
            st.download_button(
                "📥 导出静默扫货分析报告", 
                csv_data, 
                f"Silent_Scan_{selected_sector}_{datetime.now().strftime('%m%d')}.csv"
            )
