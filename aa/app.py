import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime
import requests
import json

# =================== 1. 协议穿透引擎 (支持多周期) ===================
def protocol_penetrator_sector(period="今日"):
    """
    穿透东财底层 API 获取板块资金流
    今日: f62(净额), f184(占比), f3(涨跌)
    5日: f164(净额), f165(占比), f109(涨跌)
    10日: f174(净额), f175(占比), f160(涨跌)
    """
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
        "fltt": "2", "invt": "2",
        "fid": cfg["fid"],
        "fs": "m:90+t:2+f:!50",
        "fields": cfg["fields"]
    }
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0", "Referer": "https://data.eastmoney.com/"}
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()['data']['diff']
        df = pd.DataFrame(data)
        
        # 统一字段名映射
        rename_map = {'f14': '名称', 'f12': '代码'}
        if period == "今日":
            rename_map.update({'f3': '涨跌幅', 'f62': '主力净流入-净额', 'f184': '主力净流入-净占比'})
        elif period == "5日":
            rename_map.update({'f109': '涨跌幅', 'f164': '主力净流入-净额', 'f165': '主力净流入-净占比'})
        else:
            rename_map.update({'f160': '涨跌幅', 'f174': '主力净流入-净额', 'f175': '主力净流入-净占比'})
            
        df = df.rename(columns=rename_map)
        for c in ['涨跌幅', '主力净流入-净占比']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except:
        return None

def robust_request(func, *args, **kwargs):
    """通用请求熔断器"""
    for i in range(3):
        try:
            time.sleep(random.uniform(1.2, 2.0))
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
        """核心算法：返回 0-5 整数评分"""
        if df_tick is None or df_tick.empty: return 0
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
        return int(score)

# =================== 3. UI 交互层 ===================
st.set_page_config(page_title="Sniffer Pro V8.9.3", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)
labels = ["本日", "昨日", "前日"]

st.title("🏛️ Sniffer Pro V8.9.3 - 多周期数字版")

# 侧边栏：状态监控
st.sidebar.header("📡 监控参数")
st.sidebar.metric("心跳", datetime.now().strftime('%H:%M:%S'))
target_period = st.sidebar.selectbox("资金流统计周期", ["今日", "5日", "10日"])

# --- Step 1: 板块穿透 ---
st.header(f"Step 1: {target_period}板块穿透监视")
df_sectors = protocol_penetrator_sector(period=target_period)
if df_sectors is None:
    df_sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator=target_period[:2])

if df_sectors is not None:
    # 动态调整过滤阈值 (周期长则阈值宽)
    limit_low = 0.5 if target_period == "今日" else 1.5
    limit_high = 4.0 if target_period == "今日" else 12.0
    
    target_sectors = df_sectors[(df_sectors['涨跌幅'] > limit_low) & (df_sectors['涨跌幅'] < limit_high)]
    if target_sectors.empty:
        target_sectors = df_sectors.sort_values('主力净流入-净占比', ascending=False).head(10)
    
    col1, col2 = st.columns([4, 1])
    with col1: st.dataframe(target_sectors[['名称', '代码', '涨跌幅', '主力净流入-净占比']], use_container_width=True)
    with col2: st.download_button("📥 导出板块", target_sectors.to_csv(index=False).encode('utf_8_sig'), "Sectors.csv")
else:
    st.error("无法握手数据源。")
    st.stop()

# --- Step 2: 个股审计池 ---
st.divider()
st.header("Step 2: 审计对象预选")
selected_sector = st.selectbox("选择审计板块:", ["请选择"] + target_sectors['名称'].tolist())

if selected_sector != "请选择":
    all_stocks = robust_request(ak.stock_board_industry_cons_em, symbol=selected_sector)
    if all_stocks is not None:
        quality_stocks = all_stocks[(all_stocks['涨跌幅'] < 6.0)].sort_values('换手率', ascending=False).head(15)
        selected_stocks = st.multiselect("勾选审计标的:", quality_stocks['名称'].tolist(), default=quality_stocks['名称'].tolist()[:5])
        
        # --- Step 3: 数字矩阵审计 ---
        if selected_stocks:
            st.divider()
            st.header("Step 3: 三日数字审计矩阵 (高分代表算法控盘)")
            codes = quality_stocks[quality_stocks['名称'].isin(selected_stocks)]['代码'].tolist()
            name_map = quality_stocks.set_index('代码')['名称'].to_dict()
            
            reports = []
            p_bar = st.progress(0)
            for idx, code in enumerate(codes):
                code_str = str(code).zfill(6)
                f_code = f"{'sh' if code_str.startswith('6') else 'sz'}{code_str}"
                row = {"名称": name_map.get(code), "代码": code_str}
                for i, date in enumerate(dates):
                    df_t = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
                    row[f"T-{i}_{labels[i]}({date})"] = sniffer.anti_iceberg_audit(df_t)
                reports.append(row)
                p_bar.progress((idx + 1) / len(codes))
            
            df_rep = pd.DataFrame(reports)
            score_cols = [c for c in df_rep.columns if "T-" in c]
            
            # 显示效果更好的数字矩阵
            st.dataframe(
                df_rep.style.background_gradient(cmap='RdYlGn', subset=score_cols).format(precision=0),
                use_container_width=True
            )
            
            st.download_button(
                "📥 导出完整评分报告 (包含多日得分)",
                df_rep.to_csv(index=False).encode('utf_8_sig'),
                f"Audit_{selected_sector}.csv"
            )
