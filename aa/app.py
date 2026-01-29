import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime

# =================== 1. 弹性请求引擎 ===================
def robust_request(func, *args, **kwargs):
    for i in range(3):
        try:
            res = func(*args, **kwargs)
            if res is not None: return res
        except:
            time.sleep(1.5)
    return None

# =================== 2. 反冰山审计引擎 ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        """精准锚定最近3个真实交易日"""
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df['date'] = pd.to_datetime(df['date'])
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return []

    def anti_iceberg_audit(self, df_tick):
        """反冰山算法核心：审计隐藏的静默扫货行为"""
        if df_tick is None or df_tick.empty: return 0, "无数据"
        
        # 转换时间
        df_tick['time_dt'] = pd.to_datetime(df_tick['time'], format='%H:%M:%S', errors='coerce')
        
        # 定义审计因子
        # 1. 识别中性盘成交占比 (Iceberg Ratio)
        neutral_df = df_tick[df_tick['type'] == '中性']
        n_ratio = len(neutral_df) / len(df_tick)
        
        # 2. 识别成交分布一致性 (Price Concentration)
        # 冰山算法通常在极其狭窄的价格区间内匀速吃单
        p_std = df_tick['price'].astype(float).std()
        
        # 3. 识别拆单特征 (Frag Index)
        # 统计单笔成交额分布，寻找被人工拆分成小额中性单的痕迹
        small_neutral_count = len(neutral_df[neutral_df['成交额'] < 50000])
        
        # 综合打分
        score = 0
        if n_ratio > 0.35: score += 2    # 强中性占比
        if p_std < 0.008: score += 2     # 极致静默（受控）
        if small_neutral_count > len(neutral_df) * 0.7: score += 1 # 疑似算法拆单
        
        intensity = "极高" if score >= 4 else ("高" if score >= 3 else "弱")
        return score, intensity

# =================== 3. 决策工作台 UI ===================
st.set_page_config(page_title="Sniffer Pro V7.0", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro 投行决策工作台")

if not dates:
    st.error("日期引擎启动失败")
    st.stop()

# --- 第一步：板块异常监测 ---
st.header("Step 1: 捕捉【静默流入】异常板块")
with st.status("正在扫描全市场板块资金流向...", expanded=True) as status:
    df_sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")
    # 筛选逻辑：主力净占比高，但涨幅处于“温和区”(0.5% - 3%)，避免追高过热
    target_sectors = df_sectors[
        (df_sectors['今日涨跌幅'] > 0.5) & 
        (df_sectors['今日涨跌幅'] < 3.0)
    ].sort_values('主力净流入-净占比', ascending=False).head(10)
    status.update(label="板块扫描完成", state="complete")

st.dataframe(target_sectors[['名称', '主力净流入-净占比', '今日涨跌幅', '主力净流入-净额']], use_container_width=True)

# --- 第二步：人工选定板块 + 优质个股筛选 ---
st.divider()
st.header("Step 2: 穿透精选个股 (反过热筛选)")
selected_sector = st.selectbox("请选定一个板块进行深度穿透：", ["请选择"] + target_sectors['名称'].tolist())

if selected_sector != "请选择":
    with st.spinner(f"正在分析 {selected_sector} 板块成员..."):
        all_stocks = robust_request(ak.stock_board_industry_cons_em, symbol=selected_sector)
        
        # 筛选优质股逻辑：不能过热，涨幅<4%，换手率稳定
        quality_stocks = all_stocks[
            (all_stocks['涨跌幅'] < 4.0) & 
            (all_stocks['涨跌幅'] > -1.0) &
            (all_stocks['换手率'] < 8.0)
        ].sort_values('涨跌幅', ascending=False).head(10)
        
        st.subheader(f"📍 {selected_sector} - 候选名单 (已剔除过热标的)")
        # 允许用户在候选名单中多选
        selected_stocks = st.multiselect("请选择要进行【反冰山审计】的个股：", 
                                         quality_stocks['名称'].tolist(), 
                                         default=quality_stocks['名称'].tolist()[:3])

    # --- 第三步：反冰山算法审计确认 ---
    if selected_stocks:
        st.divider()
        st.header("Step 3: 三日跨时序【反冰山审计】报告")
        
        final_data = []
        progress_bar = st.progress(0)
        
        for idx, s_name in enumerate(selected_stocks):
            s_row = quality_stocks[quality_stocks['名称'] == s_name].iloc[0]
            code = s_row['代码']
            f_code = f"{'sh' if code.startswith('6') else 'sz'}{code}"
            
            report = {"名称": s_name, "代码": code, "当前涨幅": s_row['涨跌幅']}
            
            for i, date in enumerate(dates):
                label = ["本日", "昨日", "前日"][i]
                df_tick = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
                score, intensity = sniffer.anti_iceberg_audit(df_tick)
                report[f"{label}评分"] = score
                report[f"{label}特征"] = intensity
                time.sleep(0.3)
            
            final_data.append(report)
            progress_bar.progress((idx + 1) / len(selected_stocks))
        
        df_report = pd.DataFrame(final_data)
        
        # 渲染看板
        st.dataframe(
            df_report.style.background_gradient(cmap='RdYlGn', subset=['本日评分', '昨日评分', '前日评分']),
            use_container_width=True
        )
        
        # 决策建议
        st.success("✅ 审计完成。建议关注：三日评分持续在 4 分以上且时段多为『尾盘』的标的。")

st.sidebar.caption(f"系统最后更新：{datetime.now().strftime('%H:%M:%S')}")
