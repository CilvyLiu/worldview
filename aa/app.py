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
        "fltt": "2", "invt": "2", "fid": "f62", # 按今日主力净额排序
        "fs": "m:90+t:2+f:!50",
        "fields": "f12,f14,f3,f62,f184"
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        df = pd.DataFrame(resp.json()['data']['diff']).rename(columns={
            'f12': '代码', 'f14': '板块名称', 'f3': '涨跌幅', 'f62': '主力净额', 'f184': '主力占比'
        })
        return df
    except: return None

def protocol_penetrator_stock_flow(dynamic_sector_id):
    """
    第二步：核心动态化。接收扫描出来的 sector_id，穿透该板块下的个股
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "80", "po": "1", "np": "1",
        "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
        "fltt": "2", "invt": "2", "fid": "f164", 
        "fs": f"b:{dynamic_sector_id}", # 动态传入扫描到的板块ID
        "fields": "f12,f14,f2,f3,f62,f164,f174" 
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        df = pd.DataFrame(resp.json()['data']['diff']).rename(columns={
            'f12': '代码', 'f14': '名称', 'f2': '价格', 'f3': '今日涨幅',
            'f62': '今日主力', 'f164': '5日主力', 'f174': '10日主力'
        })
        # 换算为万元
        for c in ['今日主力', '5日主力', '10日主力']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0) / 10000
        return df
    except: return None

# =================== 2. 审计核心逻辑 ===================

class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        """获取最近三个交易日"""
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: 
            return [datetime.now().strftime("%Y%m%d")]

    def silent_accumulation_audit(self, df_tick):
        """
        静默扫货审计算法：识别'低波动 + 高频率中性盘'
        """
        if df_tick is None or df_tick.empty: return 0
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        neutral_df = df_tick[df_tick['type'] == '中性']
        
        n_ratio = len(neutral_df) / len(df_tick) if len(df_tick) > 0 else 0
        p_std = df_tick['price'].std()
        
        score = 0
        # 1. 算法特征：中性盘占比极高 (主力隐藏单)
        if n_ratio > 0.40: score += 2  
        # 2. 静默特征：股价波动极小 (压盘吸筹)
        if p_std is not None and p_std < 0.005: score += 2   
        # 3. 活跃特征：小额高频成交
        small_neutral = len(neutral_df[neutral_df['成交额'] < 30000])
        if len(neutral_df) > 0 and small_neutral > len(neutral_df) * 0.7: score += 1
        return int(score)

# =================== 3. UI 交互层 ===================

st.set_page_config(page_title="Sniffer Pro V9.5", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)
labels = ["本日", "昨日", "前日"]

st.title("🏛️ Sniffer Pro V9.5 - 全网动态扫货审计")

# --- Step 1: 扫描全网板块 ---
st.header("Step 1: 穿透扫描全网强力板块 (基于主力资金)")
df_scan = protocol_penetrator_sector_scanner()

if df_scan is not None:
    # 建立 板块名 -> 代码 的映射，用于动态注入
    sector_options = df_scan.set_index('板块名称')['代码'].to_dict()
    st.dataframe(df_scan.style.background_gradient(cmap='Reds', subset=['主力净额']), use_container_width=True)
    
    # --- Step 2: 动态注入 ID 穿透个股 ---
    st.divider()
    st.header("Step 2: 穿透目标板块 (动态 ID 注入)")
    target_sector_name = st.selectbox("选择扫描到的目标板块进行审计:", ["请选择"] + list(sector_options.keys()))
    
    if target_sector_name != "请选择":
        current_sid = sector_options[target_sector_name]
        st.info(f"🚀 正在提取板块: {target_sector_name} (ID: {current_sid}) 的个股资金流...")
        
        df_stocks = protocol_penetrator_stock_flow(current_sid)
        
        if df_stocks is not None:
            # 标记静默品种：5日有大资金吸筹 且 今日涨幅 < 1% (未点火)
            df_stocks['状态预判'] = np.where(
                (df_stocks['5日主力'] > 300) & (df_stocks['今日涨幅'] < 1.0),
                "💎 静默扫货(未点火)", "正常运行"
            )
            st.dataframe(df_stocks.style.background_gradient(cmap='RdYlGn', subset=['5日主力', '10日主力']), use_container_width=True)
            
            # --- Step 3: 三日审计矩阵 ---
            st.divider()
            st.header("Step 3: 三日静默评分矩阵 (寻找启动痕迹)")
            default_selection = df_stocks[df_stocks['状态预判'].str.contains("静默")]['名称'].tolist()[:5]
            selected_stocks = st.multiselect("勾选具体审计标的:", df_stocks['名称'].tolist(), default=default_selection)
            
            if selected_stocks:
                reports = []
                p_bar = st.progress(0)
                sub_df = df_stocks[df_stocks['名称'].isin(selected_stocks)]
                
                for idx, row in sub_df.iterrows():
                    c_str = str(row['代码']).zfill(6)
                    f_code = f"{'sh' if c_str.startswith('6') else 'sz'}{c_str}"
                    
                    row_report = {
                        "名称": row['名称'], "代码": c_str, 
                        "5日主力(万)": round(row['5日主力'], 2), 
                        "今日涨幅": row['今日涨幅'],
                        "静默标记": row['状态预判']
                    }
                    
                    total_score = 0
                    for i, date in enumerate(dates):
                        try:
                            # 穿透网易 Tick 接口
                            df_t = ak.stock_zh_a_tick_163(symbol=f_code, date=date)
                            s = sniffer.silent_accumulation_audit(df_t)
                        except: s = 0
                        col_label = f"T-{i}({date})分"
                        row_report[col_label] = s
                        total_score += s
                    
                    row_report["综合吸筹评分"] = total_score
                    reports.append(row_report)
                    p_bar.progress((idx + 1) / len(sub_df))
                
                df_final = pd.DataFrame(reports)
                
                # 结果展示
                st.dataframe(
                    df_final.style.background_gradient(cmap='Greens', subset=['综合吸筹评分'])
                    .format(precision=0),
                    use_container_width=True
                )
                
                # 导出分析报告
                st.divider()
                csv_data = df_final.to_csv(index=False).encode('utf_8_sig')
                st.download_button(
                    label="📥 导出板块个股静默扫货评分报告",
                    data=csv_data,
                    file_name=f"Audit_Report_{current_sid}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv'
                )
