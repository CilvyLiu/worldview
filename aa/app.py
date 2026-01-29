import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# =================== 1. 协议穿透引擎 (Nova 专属动态版) ===================

def get_market_sectors_dynamic():
    """板块侦测：扫描全市场板块，按实时资金强度排序"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": "2", "invt": "2", "fid": "f62",
        "fs": "m:90+t:2+f:!50", 
        "fields": "f12,f14,f3,f62,f184" # f14:名称, f12:ID, f62:净额, f184:主力占比
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()['data']['diff']
        df = pd.DataFrame(data).rename(columns={
            'f12': 'ID', 'f14': '板块名称', 'f3': '今日涨幅', 
            'f62': '主力净额', 'f184': '主力占比'
        })
        # 换算单位为亿，作为板块评分
        df['板块评分'] = pd.to_numeric(df['主力净额'], errors='coerce') / 100000000
        return df.sort_values(by='板块评分', ascending=False)
    except Exception as e:
        st.error(f"板块侦测握手异常: {e}")
        return None

def get_stock_penetration(sector_id):
    """个股侦测：穿透指定板块下的所有个股"""
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
        """Nova 核心审计算法"""
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

# =================== 3. 动态侦测 UI ===================

st.set_page_config(page_title="Sniffer Pro V12.0", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro V12.0 - 动态全向侦测与复盘系统")

# --- Step 1: 实时板块侦测 ---
st.header("Step 1: 全市场板块资金侦测")
df_all_sectors = get_market_sectors_dynamic()

if df_all_sectors is not None:
    st.sidebar.header("📂 审计配置")
    st.sidebar.info(f"审计日期范围: {', '.join(dates)}")
    
    st.dataframe(
        df_all_sectors, 
        use_container_width=True,
        column_config={"板块评分": st.column_config.NumberColumn(format="%.2f 亿 🟢")}
    )
    
    # 【导出按钮 1】
    csv_step1 = df_all_sectors.to_csv(index=False).encode('utf_8_sig')
    st.download_button(
        label="📥 导出全市场板块资金侦测报告",
        data=csv_step1,
        file_name=f"Nova_Market_Sectors_{datetime.now().strftime('%m%d')}.csv",
        mime='text/csv'
    )
    
    st.divider()
    sector_map = df_all_sectors.set_index('板块名称')['ID'].to_dict()
    selected_sector_name = st.selectbox("🎯 选定待审计板块:", ["请选择探测目标"] + list(sector_map.keys()))

    if selected_sector_name != "请选择探测目标":
        sid = sector_map[selected_sector_name]
        sec_info = df_all_sectors[df_all_sectors['板块名称'] == selected_sector_name].iloc[0]
        
        # --- Step 2: 个股穿透侦测 ---
        st.header(f"Step 2: {selected_sector_name} - 个股穿透侦测")
        df_stocks = get_stock_penetration(sid)
        
        if df_stocks is not None:
            df_stocks['侦测状态'] = np.where(
                (df_stocks['5日主力'] > 500) & (df_stocks['今日涨幅'] < 1.5), "💎 疑似静默扫货", "正常波动"
            )
            st.dataframe(df_stocks, use_container_width=True)

            # 【导出按钮 2】
            csv_step2 = df_stocks.to_csv(index=False).encode('utf_8_sig')
            st.download_button(
                label=f"📥 导出 {selected_sector_name} 个股明细报告",
                data=csv_step2,
                file_name=f"Nova_Stocks_{selected_sector_name}_{datetime.now().strftime('%m%d')}.csv",
                mime='text/csv'
            )

            # --- Step 3: 深度审计与综合导出 ---
            st.divider()
            st.header("Step 3: 三日深度审计与综合导出")
            targets = st.multiselect(
                "勾选标的执行深度 Tick 审计:", 
                df_stocks['名称'].tolist(),
                default=df_stocks[df_stocks['侦测状态']=="💎 疑似静默扫货"]['名称'].tolist()[:3]
            )
            
            if targets:
                reports = []
                p_bar = st.progress(0)
                selected_df = df_stocks[df_stocks['名称'].isin(targets)]
                
                for idx, (s_idx, row) in enumerate(selected_df.iterrows()):
                    c_str = str(row['代码']).zfill(6)
                    f_code = f"{'sh' if c_str.startswith('6') else 'sz'}{c_str}"
                    
                    report_row = {
                        "板块名称": selected_sector_name,
                        "板块今日强度(亿)": round(sec_info['板块评分'], 2),
                        "标的名称": row['名称'], "代码": c_str,
                        "今日涨幅%": row['今日涨幅'], "5日主力(万)": row['5日主力']
                    }
                    
                    total_s = 0
                    for d_idx, date in enumerate(dates):
                        try:
                            df_t = ak.stock_zh_a_tick_163(symbol=f_code, date=date)
                            s = sniffer.analyze_silent_trace(df_t)
                        except: s = 0
                        report_row[f"T-{d_idx}({date})审计分"] = s
                        total_s += s
                    
                    report_row["审计综合总分"] = total_s
                    reports.append(report_row)
                    p_bar.progress((idx + 1) / len(selected_df))
                
                df_rep = pd.DataFrame(reports)
                st.subheader("📊 最终复盘矩阵")
                st.dataframe(df_rep.style.background_gradient(subset=['审计综合总分'], cmap='RdYlGn'), use_container_width=True)

                # 【导出按钮 3】
                csv_step3 = df_rep.to_csv(index=False).encode('utf_8_sig')
                st.download_button(
                    label=f"📥 导出 {selected_sector_name} 三日深度审计综合报告", 
                    data=csv_step3,
                    file_name=f"Nova_Audit_Final_{selected_sector_name}_{datetime.now().strftime('%m%d')}.csv",
                    mime='text/csv',
                    use_container_width=True
                )
