import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime
import plotly.graph_objects as go

# =================== 1. 仿人弹性请求引擎 ===================
def robust_request(func, *args, **kwargs):
    """确保数据新鲜度：随机延迟 + 多轮重试"""
    for i in range(3):
        try:
            time.sleep(random.uniform(1.2, 2.0))  # 模拟真人访问
            res = func(*args, **kwargs)
            if res is not None and not (isinstance(res, pd.DataFrame) and res.empty):
                return res
        except:
            continue
    return None

@st.cache_data(ttl=60)
def convert_df(df):
    """CSV 导出编码"""
    return df.to_csv(index=False).encode('utf_8_sig')

# =================== 2. 核心反冰山审计 ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        """获取最近 count 个交易日"""
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df['date'] = pd.to_datetime(df['date'])
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except:
            return []

    def anti_iceberg_audit(self, df_tick):
        """反冰山算法，返回 score + 多维特征"""
        if df_tick is None or df_tick.empty:
            return 0, 0, 0, 0
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        neutral_df = df_tick[df_tick['type']=='中性']
        
        n_ratio = len(neutral_df)/len(df_tick) if len(df_tick)>0 else 0
        p_std = df_tick['price'].std() if len(df_tick)>1 else 0
        frag_count = len(neutral_df[neutral_df['成交额']<50000])
        
        score = 0
        if n_ratio > 0.35: score += 2
        if p_std < 0.008: score += 2
        if len(neutral_df)>0 and frag_count > len(neutral_df)*0.7: score +=1
        
        return score, n_ratio, p_std, frag_count

# =================== 3. 批量 Tick 获取 ===================
def batch_tick_request(codes, dates):
    tick_dict = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    for idx, code in enumerate(codes):
        code_str = str(code).zfill(6)
        f_code = f"{'sh' if code_str.startswith('6') else 'sz'}{code_str}"
        tick_dict[code] = {}
        for date in dates:
            status_text.text(f"🚀 正在获取: {code_str} | 日期: {date}")
            tick_dict[code][date] = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
        progress_bar.progress((idx+1)/len(codes))
    status_text.empty()
    return tick_dict

def multi_day_audit(tick_dict, dates, sniffer, name_map):
    reports = []
    for code, day_data in tick_dict.items():
        code_str = str(code).zfill(6)
        row = {"名称": name_map.get(code, "未知"), "代码": code_str}
        for i, date in enumerate(dates):
            df_tick = day_data.get(date)
            score, n_ratio, p_std, frag_count = sniffer.anti_iceberg_audit(df_tick)
            row[f"T-{i}评分"] = score
            row[f"T-{i}中性占比"] = round(n_ratio,3)
            row[f"T-{i}价格Std"] = round(p_std,4)
            row[f"T-{i}小单占比"] = round(frag_count/len(df_tick) if df_tick is not None and len(df_tick)>0 else 0,3)
        reports.append(row)
    return pd.DataFrame(reports)

# =================== 4. Streamlit UI ===================
st.set_page_config(page_title="Sniffer Pro V9 - 全维穿透版", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)
labels = ["本日", "昨日", "前日"]

st.title("🏛️ Sniffer Pro V9 - 投行级全维嗅探系统")

if not dates:
    st.error("🔴 无法同步交易日历，请检查网络或 API")
    st.stop()

# --- Step 1: 板块监测 ---
st.header("Step 1: 捕捉【静默流入】板块")
raw_sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")
if raw_sectors is None:
    st.error("接口被封锁，请更换 IP 或稍后再试")
    st.stop()

df_s = raw_sectors.copy()
df_s = df_s.rename(columns=lambda x: x.strip().replace('今日','').replace('涨跌幅','涨跌幅'))
df_s['涨跌幅'] = pd.to_numeric(df_s['涨跌幅'], errors='coerce').fillna(0)
df_s['主力净流入-净占比'] = pd.to_numeric(df_s['主力净流入-净占比'], errors='coerce').fillna(0)

# 自适应筛选板块
target_sectors = df_s[(df_s['涨跌幅']>0.3) & (df_s['涨跌幅']<6.0)]
target_sectors = target_sectors.sort_values('主力净流入-净占比', ascending=False).head(10)
st.dataframe(target_sectors[['名称','主力净流入-净占比','涨跌幅']], use_container_width=True)

csv_sector = convert_df(target_sectors)
st.download_button(label="📥 导出板块监测 (CSV)", data=csv_sector, file_name=f"Sectors_{dates[0]}.csv", mime='text/csv')

# --- Step 2: 个股穿透 ---
st.divider()
st.header("Step 2: 个股穿透与筛选")
selected_sector = st.selectbox("选择板块:", ["请选择"] + target_sectors['名称'].tolist())
if selected_sector != "请选择":
    stocks = robust_request(ak.stock_board_industry_cons_em, symbol=selected_sector)
    if stocks is None:
        st.error("个股接口失败，请稍后再试")
        st.stop()
    
    stocks['涨跌幅'] = pd.to_numeric(stocks['涨跌幅'], errors='coerce')
    stocks['换手率'] = pd.to_numeric(stocks['换手率'], errors='coerce').fillna(0)
    
    q_stocks = stocks[(stocks['涨跌幅']<6.0)&(stocks['涨跌幅']>-2.0)&(stocks['换手率']>0.3)&(stocks['换手率']<15.0)]
    q_stocks = q_stocks.sort_values('换手率', ascending=False)
    
    st.subheader(f"📍 {selected_sector} 候选池")
    picked = st.multiselect("勾选审计对象:", q_stocks['名称'].tolist(), default=q_stocks['名称'].tolist()[:3])
    
    # --- Step 3: 三日跨时序审计 ---
    if picked:
        st.divider()
        st.header("Step 3: 三日反冰山审计报告")
        codes = q_stocks[q_stocks['名称'].isin(picked)]['代码'].tolist()
        name_map = q_stocks.set_index('代码')['名称'].to_dict()
        tick_dict = batch_tick_request(codes, dates)
        df_report = multi_day_audit(tick_dict, dates, sniffer, name_map)
        
        # 高对比度表格
        score_cols = [f"T-{i}评分" for i in range(len(dates))]
        st.dataframe(df_report.style.background_gradient(cmap='RdYlGn', subset=score_cols), use_container_width=True)
        
        csv_report = convert_df(df_report)
        st.download_button(label="📥 导出审计明细 (CSV)", data=csv_report, file_name=f"Audit_{selected_sector}_{dates[0]}.csv", mime='text/csv')
        
        # --- Step 4: 雷达图可视化 ---
        st.divider()
        st.header("Step 4: 高分标的雷达图")
        high_score_df = df_report[df_report[score_cols].max(axis=1)>=2]
        if not high_score_df.empty:
            cols = st.columns(3)
            for i, (_, r) in enumerate(high_score_df.iterrows()):
                with cols[i%3]:
                    fig = go.Figure(go.Scatterpolar(
                        r=[r[c] for c in score_cols],
                        theta=labels,
                        fill='toself'
                    ))
                    fig.update_layout(title=r['名称'], polar=dict(radialaxis=dict(range=[0,5])), height=300)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂未发现明显反冰山特征标的")
