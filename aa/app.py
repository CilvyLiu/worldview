import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime
import plotly.graph_objects as go
import requests
import re

# =================== 1. 投行级仿人请求引擎 ===================
def sniper_direct_protocol_sector():
    """
    直接穿透：模拟底层 push2 协议获取板块资金流
    """
    # 这是东财最底层的实时数据接口，权重极高，不易被封
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    
    params = {
        "pn": "1",
        "pz": "50",
        "po": "1",
        "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5", # 使用你之前抓到的令牌
        "fltt": "2",
        "invt": "2",
        "fid": "f62", # 主力净流入排序
        "fs": "m:90+t:2+f:!50",
        "fields": "f12,f14,f2,f3,f62,f184"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://data.eastmoney.com/bkzj/hy.html",
        "Accept": "*/*"
    }

    try:
        # 增加随机拨号延迟
        time.sleep(random.uniform(2, 4))
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        # 自动脱掉 jQuery 壳
        text = response.text
        if "jQuery" in text:
            text = text[text.find("(")+1 : text.rfind(")")]
            
        data = json.loads(text)
        df = pd.DataFrame(data['data']['diff'])
        
        # 字段重映射
        df = df.rename(columns={
            'f14': '名称', 'f12': '代码', 
            'f3': '今日涨跌幅', 'f62': '主力净流入-净额', 
            'f184': '主力净流入-净占比'
        })
        
        # 数值清洗
        for col in ['今日涨跌幅', '主力净流入-净占比']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        return df
    except Exception as e:
        return None

# --- 在主程序中使用 ---
st.header("Step 1: 协议层穿透监控")
df_sectors = sniper_direct_protocol_sector()

if df_sectors is not None:
    # 自动定标准：涨幅 0.5% - 4%
    target_sectors = df_sectors[(df_sectors['今日涨跌幅'] > 0.5) & (df_sectors['今日涨跌幅'] < 4.0)]
    target_sectors = target_sectors.sort_values('主力净流入-净占比', ascending=False).head(10)
    st.dataframe(target_sectors[['名称', '今日涨跌幅', '主力净流入-净占比']], use_container_width=True)
else:
    st.error("🚨 协议层握手失败。建议：1. 开启手机热点更换 IP；2. 等待 15 分钟待 WAF 自动解锁。")

# =================== 2. 核心审计类 (逻辑加固) ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        """锁定最近3个真实交易日"""
        try:
            # 使用指数日线作为日历基准，这是最稳定的方法
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df['date'] = pd.to_datetime(df['date'])
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except:
            return []

    def anti_iceberg_audit(self, df_tick):
        """反冰山指纹审计：中性盘占比 + 价格稳定性 + 拆单频率"""
        if df_tick is None or df_tick.empty: 
            return 0, "数据缺口"
        
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        
        # 核心算法：识别“静默扫货”
        neutral_df = df_tick[df_tick['type'] == '中性']
        total_len = len(df_tick)
        n_ratio = len(neutral_df) / total_len if total_len > 0 else 0
        p_std = df_tick['price'].std()
        
        # 拆单特征识别 (小额中性单高频出现)
        small_neutral_count = len(neutral_df[neutral_df['成交额'] < 50000])
        
        score = 0
        if n_ratio > 0.35: score += 2    # 中性盘主力化
        if p_std is not None and p_std < 0.008: score += 2  # 价格走势异常平滑
        if len(neutral_df) > 0 and small_neutral_count > len(neutral_df) * 0.7: 
            score += 1 # 算法拆单痕迹
        
        intensity = "极高" if score >= 4 else ("高" if score >= 2 else "弱")
        return score, intensity

# =================== 3. 批量 Tick 获取 (分段控制逻辑) ===================
def batch_tick_request(codes, dates):
    """批量预取，加入分段休眠防止 IP 封锁"""
    tick_dict = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, code in enumerate(codes):
        # 每处理 3 只股票，额外休息一段时间，模拟人类整理笔记
        if idx > 0 and idx % 3 == 0:
            time.sleep(random.uniform(3, 6))
            
        code_str = str(code).zfill(6)
        f_code = f"{'sh' if code_str.startswith('6') else 'sz'}{code_str}"
        tick_dict[code] = {}
        
        for date in dates:
            status_text.text(f"🔍 协议穿透审计中: {code_str} ({date})")
            tick_dict[code][date] = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
            
        progress_bar.progress((idx + 1) / len(codes))
    
    status_text.empty()
    return tick_dict

# =================== 4. Streamlit UI ===================
st.set_page_config(page_title="Sniffer Pro V8.8", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)
labels = ["本日", "昨日", "前日"]

st.title("🏛️ Sniffer Pro V8.8 - 投行级仿人嗅探台")

if not dates:
    st.error("⚠️ 核心日历握手失败。请检查网络环境，或尝试手动更新 Akshare。")
    st.stop()

# 侧边栏：监控状态
st.sidebar.header("🗓️ 审计窗口")
for i, d in enumerate(dates):
    st.sidebar.metric(f"{labels[i]} (T-{i})", d)
st.sidebar.caption(f"系统指纹已重置 | {datetime.now().strftime('%H:%M:%S')}")

# --- Step 1: 板块监测 ---
st.header("Step 1: 捕捉【静默流入】异常板块")
# 尝试获取板块数据
df_sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")

if df_sectors is not None:
    df_sectors.columns = [c.replace('今日','').replace('涨跌幅','今日涨跌幅') for c in df_sectors.columns]
    df_sectors['今日涨跌幅'] = pd.to_numeric(df_sectors['今日涨跌幅'], errors='coerce').fillna(0)
    df_sectors['主力净流入-净占比'] = pd.to_numeric(df_sectors['主力净流入-净占比'], errors='coerce').fillna(0)
    
    # 自动定标准逻辑
    target_sectors = df_sectors[(df_sectors['今日涨跌幅'] > 0.5) & (df_sectors['今日涨跌幅'] < 4.0)]
    if target_sectors.empty:
        target_sectors = df_sectors.sort_values('主力净流入-净占比', ascending=False).head(10)
    else:
        target_sectors = target_sectors.sort_values('主力净流入-净占比', ascending=False).head(10)
        
    st.dataframe(target_sectors[['名称', '主力净流入-净占比', '今日涨跌幅']], use_container_width=True)
else:
    st.error("🔴 板块接口由于 IP 受限未能响应。")
    st.stop()

# --- Step 2: 个股筛选 ---
st.divider()
st.header("Step 2: 穿透精选个股 (反过热筛选)")
selected_sector = st.selectbox("选择板块开启三日审计:", ["请选择"] + target_sectors['名称'].tolist())

if selected_sector != "请选择":
    all_stocks = robust_request(ak.stock_board_industry_cons_em, symbol=selected_sector)
    if all_stocks is not None:
        all_stocks['涨跌幅'] = pd.to_numeric(all_stocks['涨跌幅'], errors='coerce').fillna(0)
        all_stocks['换手率'] = pd.to_numeric(all_stocks['换手率'], errors='coerce').fillna(0)
        
        # 排除已经大涨/过热的标的
        quality_stocks = all_stocks[
            (all_stocks['涨跌幅'] < 5.0) & (all_stocks['涨跌幅'] > -2.0) & (all_stocks['换手率'] < 10.0)
        ].sort_values('换手率', ascending=False).head(15)
        
        st.subheader(f"📍 {selected_sector} - 审计池")
        selected_stocks = st.multiselect("请选取需要穿透的标的：", 
                                         quality_stocks['名称'].tolist(), 
                                         default=quality_stocks['名称'].tolist()[:3])
        
        # --- Step 3: 三日跨时序审计 ---
        if selected_stocks:
            st.divider()
            st.header("Step 3: 三日跨时序【反冰山审计】")
            
            name_map = quality_stocks.set_index('代码')['名称'].to_dict()
            codes = quality_stocks[quality_stocks['名称'].isin(selected_stocks)]['代码'].tolist()
            
            tick_dict = batch_tick_request(codes, dates)
            
            # 使用多日审计函数
            reports = []
            for code, day_data in tick_dict.items():
                code_str = str(code).zfill(6)
                report = {"名称": name_map.get(code, "未知"), "代码": code_str}
                for i, date in enumerate(dates):
                    df_tick = day_data.get(date)
                    score, intensity = sniffer.anti_iceberg_audit(df_tick)
                    report[f"T-{i}评分"] = score
                reports.append(report)
            
            df_report = pd.DataFrame(reports)
            
            score_cols = [f"T-{i}评分" for i in range(len(dates))]
            st.dataframe(
                df_report.style.background_gradient(cmap='RdYlGn', subset=score_cols), 
                use_container_width=True
            )

            # --- Step 4: 雷达图 ---
            st.divider()
            st.header("Step 4: 算法指纹稳定性分析")
            cols = st.columns(3)
            for idx, (_, row) in enumerate(df_report.iterrows()):
                with cols[idx % 3]:
                    fig = go.Figure()
                    fig.add_trace(go.Scatterpolar(
                        r=[row[c] for c in score_cols],
                        theta=labels,
                        fill='toself',
                        name=row['名称']
                    ))
                    fig.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
                        title=f"{row['名称']} ({row['代码']})",
                        height=350
                    )
                    st.plotly_chart(fig, use_container_width=True)
