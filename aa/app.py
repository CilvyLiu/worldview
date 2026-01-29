import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime
import requests

# =================== 1. 协议穿透引擎 (Nova 专属) ===================
def get_safe_sectors():
    """安全获取板块列表，自动修正列名"""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日")
        # 模糊匹配：只要包含'名称'或'代码'的列就抓出来
        name_col = [c for c in df.columns if '名称' in c][0]
        code_col = [c for c in df.columns if '代码' in c][0]
        return df, name_col, code_col
    except Exception as e:
        st.error(f"板块数据握手失败: {e}")
        return None, None, None

def protocol_penetrator_stock_flow(sector_id="BK0732"):
    """使用 Nova 提供的穿透地址，获取个股深度资金流"""
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

# =================== 2. 扫货痕迹审计核心 ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return []

    def analyze_silent_trace(self, df_tick):
        """
        核心算法：高频小单中性盘 + 极低价格波动 = 庄家算法吸筹
        """
        if df_tick is None or df_tick.empty: return 0
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        
        neutral_df = df_tick[df_tick['type'] == '中性']
        n_ratio = len(neutral_df) / len(df_tick) if len(df_tick) > 0 else 0
        p_std = df_tick['price'].std()
        
        score = 0
        if n_ratio > 0.40: score += 2 
        if p_std is not None and p_std < 0.005: score += 2  
        small_amt_ratio = len(neutral_df[neutral_df['成交额'] < 30000]) / len(neutral_df) if len(neutral_df) > 0 else 0
        if small_amt_ratio > 0.8: score += 1 
        return score

# =================== 3. UI 展现层 ===================
st.set_page_config(page_title="Sniffer Pro V9.8", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro V9.8 - 静默扫货审计系统")

# --- 侧边栏：导入与配置 ---
st.sidebar.header("📂 数据中心")
uploaded_file = st.sidebar.file_uploader("导入历史审计报告 (CSV)", type="csv")
if uploaded_file:
    st.sidebar.success("历史数据已载入")
    # 可选：展示历史对比逻辑

# --- Step 1: 板块穿透逻辑 ---
df_sectors, name_col, code_col = get_safe_sectors()

if df_sectors is not None:
    sector_map = df_sectors.set_index(name_col)[code_col].to_dict()
    
    st.header("Step 1: 全网板块穿透")
    selected_sector = st.selectbox("选择监控板块:", ["请选择"] + list(sector_map.keys()))

    if selected_sector != "请选择":
        sid = sector_map[selected_sector]
        
        # 自动计算板块评分 (基于主力占比)
        sector_score = float(df_sectors[df_sectors[name_col]==selected_sector]['主力净额'].iloc[0]) / 10000
        
        df_stocks = protocol_penetrator_stock_flow(sid)
        
        if df_stocks is not None:
            df_stocks['启动状态'] = np.where(
                (df_stocks['5日主力'] > 500) & (df_stocks['今日涨幅'] < 1.5), 
                "💎 静默扫货", "正常波动"
            )
            st.subheader(f"📍 {selected_sector} (评分: {sector_score:.2f}万) 资金流看板")
            # 兼容性渲染：改用原生 column_config 避免 matplotlib 缺失错误
            st.dataframe(df_stocks, use_container_width=True, column_config={
                "5日主力": st.column_config.ProgressColumn(min_value=0, max_value=5000, format="%.0f万"),
                "今日涨幅": st.column_config.NumberColumn(format="%.2f%%")
            })

            # --- Step 2: 审计 ---
            st.divider()
            st.header("Step 2: 三日个股扫货痕迹审计")
            targets = st.multiselect("勾选标的进行深度审计:", df_stocks['名称'].tolist(), 
                                    default=df_stocks[df_stocks['启动状态']=="💎 静默扫货"]['名称'].tolist()[:5])
            
            if targets:
                reports = []
                p_bar = st.progress(0)
                selected_df = df_stocks[df_stocks['名称'].isin(targets)]
                
                for idx, row in selected_df.iterrows():
                    code_str = str(row['代码']).zfill(6)
                    f_code = f"{'sh' if code_str.startswith('6') else 'sz'}{code_str}"
                    
                    report_row = {
                        "板块": selected_sector,
                        "板块评分": round(sector_score, 2),
                        "名称": row['名称'], "代码": code_str, "状态": row['启动状态'],
                        "5日主力(万)": row['5日主力'], "今日涨幅": row['今日涨幅']
                    }
                    
                    matrix_scores = []
                    for i, date in enumerate(dates):
                        try:
                            # 穿透网易 Tick 接口
                            df_t = ak.stock_zh_a_tick_163(symbol=f_code, date=date)
                            s = sniffer.analyze_silent_trace(df_t)
                        except: s = 0
                        report_row[f"T-{i}({date})"] = s
                        matrix_scores.append(s)
                    
                    report_row["综合扫货强度"] = sum(matrix_scores)
                    reports.append(report_row)
                    p_bar.progress((idx + 1) / len(selected_df))
                
                df_rep = pd.DataFrame(reports)
                
                # 展现最终审计矩阵
                st.subheader("📊 审计评分矩阵")
                st.dataframe(df_rep, use_container_width=True)
                
                # --- Step 3: 导出 ---
                st.divider()
                st.header("Step 3: 导出综合报告")
                csv_data = df_rep.to_csv(index=False).encode('utf_8_sig')
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📥 导出审计报告 (含板块评分)", 
                        data=csv_data, 
                        file_name=f"Nova_Audit_{selected_sector}_{datetime.now().strftime('%m%d')}.csv",
                        mime='text/csv'
                    )
                with col2:
                    st.info("💡 提示：导出的报告包含板块及个股的三日评分，可再次通过侧边栏导入进行对比。")
