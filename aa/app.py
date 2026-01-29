import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime

# =================== 1. 弹性请求引擎 ===================
def robust_request(func, *args, **kwargs):
    retries = 3
    for i in range(retries):
        try:
            res = func(*args, **kwargs)
            if res is not None: return res
        except:
            time.sleep(1.5)
    return None

# =================== 2. 反冰山审计引擎 ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        """核心：通过指数日线确保获取的是真实的交易日期，无视当前是否为节假日"""
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df['date'] = pd.to_datetime(df['date'])
            # 返回最近的 N 个交易日并降序 [T, T-1, T-2]
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except Exception as e:
            st.error(f"日期引擎异常: {e}")
            return []

    def anti_iceberg_audit(self, df_tick):
        """反冰山算法核心：审计隐藏的静默扫货行为"""
        if df_tick is None or df_tick.empty: return 0, "无数据"
        
        # 预处理：转换时间及数值类型
        df_tick['time_dt'] = pd.to_datetime(df_tick['time'], format='%H:%M:%S', errors='coerce')
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        
        # 1. 识别中性盘成交占比
        neutral_df = df_tick[df_tick['type'] == '中性']
        n_ratio = len(neutral_df) / len(df_tick) if len(df_tick) > 0 else 0
        
        # 2. 识别成交分布一致性 (冰山单通常在极窄区间成交)
        p_std = df_tick['price'].std()
        
        # 3. 识别小额中性拆单特征
        small_neutral_count = len(neutral_df[neutral_df['成交额'] < 50000])
        
        score = 0
        if n_ratio > 0.35: score += 2    # 强中性占比
        if p_std is not None and p_std < 0.008: score += 2  # 价格受控
        if len(neutral_df) > 0 and small_neutral_count > len(neutral_df) * 0.7: score += 1 # 算法拆单
        
        intensity = "极高" if score >= 4 else ("高" if score >= 3 else "弱")
        return score, intensity

# =================== 3. 决策工作台 UI ===================
st.set_page_config(page_title="Sniffer Pro V7.3", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro 投行决策工作台")

if not dates:
    st.error("❌ 无法确定交易日期，系统挂起。请检查网络。")
    st.stop()

# --- 日期展示区：侧边栏与主界面同步保留 ---
st.sidebar.header("🗓️ 审计交易日序列")
labels = ["本日", "昨日", "前日"]
for i, d in enumerate(dates):
    st.sidebar.metric(f"{labels[i]} (T-{i})", d)

cols = st.columns(3)
for i, d in enumerate(dates):
    cols[i].info(f"📅 **{labels[i]}日期**: {d}")

# --- 第一步：板块异常监测 ---
st.header("Step 1: 捕捉【静默流入】异常板块")
with st.status("正在扫描全市场板块资金流向...", expanded=True) as status:
    df_sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")
    if df_sectors is not None:
        # 【核心修复】解决 TypeError：强制转换类型
        df_sectors['今日涨跌幅'] = pd.to_numeric(df_sectors['今日涨跌幅'], errors='coerce')
        df_sectors['主力净流入-净占比'] = pd.to_numeric(df_sectors['主力净流入-净占比'], errors='coerce')
        
        # 逻辑：资金强流入 但 涨幅未过热
        target_sectors = df_sectors[
            (df_sectors['今日涨跌幅'] > 0.5) & 
            (df_sectors['今日涨跌幅'] < 3.0)
        ].sort_values('主力净流入-净占比', ascending=False).head(10)
        
        status.update(label="板块扫描完成", state="complete")
        st.dataframe(target_sectors[['名称', '主力净流入-净占比', '今日涨跌幅', '主力净流入-净额']], use_container_width=True)
    else:
        st.error("获取板块数据失败")
        st.stop()

# --- 第二步：人工选定板块 + 优质个股筛选 ---
st.divider()
st.header("Step 2: 穿透精选个股 (反过热筛选)")
selected_sector = st.selectbox("请选定一个板块进行深度穿透：", ["请选择"] + target_sectors['名称'].tolist())

if selected_sector != "请选择":
    with st.spinner(f"正在穿透 {selected_sector} 板块成员..."):
        all_stocks = robust_request(ak.stock_board_industry_cons_em, symbol=selected_sector)
        if all_stocks is not None:
            all_stocks['涨跌幅'] = pd.to_numeric(all_stocks['涨跌幅'], errors='coerce')
            all_stocks['换手率'] = pd.to_numeric(all_stocks['换手率'], errors='coerce')
            
            # 筛选优质股：涨幅在 -1.5% 到 4% 之间，剔除换手过高的妖股
            quality_stocks = all_stocks[
                (all_stocks['涨跌幅'] < 4.0) & 
                (all_stocks['涨跌幅'] > -1.5) &
                (all_stocks['换手率'] < 8.0)
            ].sort_values('涨跌幅', ascending=False).head(15)
            
            st.subheader(f"📍 {selected_sector} - 潜伏候选名单 (已对齐 T-0 到 T-2)")
            selected_stocks = st.multiselect("请选择需要『反冰山审计』的股票：", 
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
            
            # 依次回溯选定的物理日期
            for i, date in enumerate(dates):
                label = labels[i]
                df_tick = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
                score, intensity = sniffer.anti_iceberg_audit(df_tick)
                report[f"{label}评分"] = score
                report[f"{label}指纹"] = intensity
                time.sleep(0.4)
            
            final_data.append(report)
            progress_bar.progress((idx + 1) / len(selected_stocks))
        
        df_report = pd.DataFrame(final_data)
        # 渲染动态热力看板
        st.dataframe(
            df_report.style.background_gradient(cmap='RdYlGn', subset=[f"{l}评分" for l in labels]),
            use_container_width=True
        )
        st.success(f"✅ 审计报告已生成。基准物理日期序列：{', '.join(dates)}")

st.sidebar.caption(f"系统运行中 | {datetime.now().strftime('%H:%M:%S')}")
