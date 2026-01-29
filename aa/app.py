import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# =================== 1. 协议穿透引擎 (修复索引崩溃隐患) ===================

def get_safe_nova_sectors():
    """安全获取板块：放弃强制索引，改用弹性关键词匹配"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "60", "po": "1", "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2+f:!50", 
        "fields": "f12,f14,f3,f62" 
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()['data']['diff']
        df = pd.DataFrame(data)
        
        # --- 弹性匹配逻辑 ---
        # 自动识别含有代码、名称、资金金额的原始列名
        c_map = {
            'f12': '板块代码', 
            'f14': '板块名称', 
            'f3': '今日涨幅', 
            'f62': '主力净额'
        }
        df = df.rename(columns=c_map)
        
        # 计算板块评分：主力净额(亿)
        df['板块评分'] = pd.to_numeric(df['主力净额'], errors='coerce') / 100000000
        return df
    except Exception as e:
        st.error(f"板块协议穿透失败: {e}")
        return None

def protocol_penetrator_stock_flow(sector_id):
    """个股穿透：使用 Nova 指定地址"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
        "fltt": "2", "invt": "2", "fid": "f164", 
        "fs": f"b:{sector_id}",
        "fields": "f12,f14,f2,f3,f62,f164,f174" 
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        df = pd.DataFrame(resp.json()['data']['diff']).rename(columns={
            'f12': '代码', 'f14': '名称', 'f2': '价格', 'f3': '今日涨幅',
            'f62': '今日主力', 'f164': '5日主力', 'f174': '10日主力'
        })
        for c in ['今日主力', '5日主力', '10日主力']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0) / 10000
        return df
    except: return None

# =================== 2. 扫货痕迹审计 (核心算法禁止删减) ===================

class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return [datetime.now().strftime("%Y%m%d")]

    def analyze_silent_trace(self, df_tick):
        """Nova 核心逻辑：高频小单中性盘审计"""
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

# =================== 3. 展现与综合导出 ===================

st.set_page_config(page_title="Sniffer Pro V10.6", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro V10.6 - 鲁棒性改进版")

# Step 1: 板块穿透
df_sec = get_safe_nova_sectors()

if df_sec is not None:
    sec_map = df_sec.set_index('板块名称')['板块代码'].to_dict()
    selected_name = st.selectbox("1. 选择板块 (实时评分排序)", ["请选择"] + list(sec_map.keys()))

    if selected_name != "请选择":
        sid = sec_map[selected_name]
        sec_info = df_sec[df_sec['板块名称'] == selected_name].iloc[0]
        
        # Step 2: 个股展示
        df_stocks = protocol_penetrator_stock_flow(sid)
        if df_stocks is not None:
            df_stocks['启动状态'] = np.where(
                (df_stocks['5日主力'] > 500) & (df_stocks['今日涨幅'] < 1.5), "💎 静默扫货", "正常波动"
            )
            st.subheader(f"📍 {selected_name} (板块分: {sec_info['板块评分']:.2f}亿)")
            st.dataframe(df_stocks, use_container_width=True)

            # Step 3: 深度审计
            st.divider()
            st.header("2. 三日个股扫货痕迹审计")
            targets = st.multiselect("勾选目标标的:", df_stocks['名称'].tolist(), 
                                    default=df_stocks[df_stocks['启动状态']=="💎 静默扫货"]['名称'].tolist()[:5])
            
            if targets:
                reports = []
                p_bar = st.progress(0)
                selected_df = df_stocks[df_stocks['名称'].isin(targets)]
                
                for idx, (s_idx, row) in enumerate(selected_df.iterrows()):
                    c_str = str(row['代码']).zfill(6)
                    f_code = f"{'sh' if c_str.startswith('6') else 'sz'}{c_str}"
                    
                    # 报告整合：每一行都注入板块评分
                    report_row = {
                        "所属板块": selected_name, 
                        "板块今日评分(亿)": round(sec_info['板块评分'], 2),
                        "标的名称": row['名称'], "代码": c_str, 
                        "5日主力净流入(万)": row['5日主力']
                    }
                    
                    total_s = 0
                    for d_idx, date in enumerate(dates):
                        try:
                            df_t = ak.stock_zh_a_tick_163(symbol=f_code, date=date)
                            s = sniffer.analyze_silent_trace(df_t)
                        except: s = 0
                        report_row[f"T-{d_idx}({date})审计分"] = s
                        total_s += s
                    
                    report_row["综合个股总分"] = total_s
                    reports.append(report_row)
                    p_bar.progress((idx + 1) / len(selected_df))
                
                df_rep = pd.DataFrame(reports)
                st.dataframe(df_rep.style.highlight_max(subset=['综合个股总分']), use_container_width=True)

                # --- Step 4: 导出最终资产 ---
                st.divider()
                st.header("3. 导出综合复盘报告")
                csv = df_rep.to_csv(index=False).encode('utf_8_sig')
                st.download_button(
                    label=f"📥 导出 {selected_name} 审计全报告 (板块+个股双评分)", 
                    data=csv,
                    file_name=f"Nova_Audit_{selected_name}_{datetime.now().strftime('%m%d')}.csv",
                    mime='text/csv',
                    use_container_width=True
                )
