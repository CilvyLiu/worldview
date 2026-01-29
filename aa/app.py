import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime

# =================== 1. 底层请求引擎 ===================
def robust_request(func, *args, **kwargs):
    """对抗断连的弹性引擎：确保高频请求下的稳定性"""
    retries = 3
    for i in range(retries):
        try:
            res = func(*args, **kwargs)
            if res is not None: return res
        except:
            time.sleep(1.5)
    return None

# =================== 2. 审计核心类 ===================
class InstitutionalSniffer:
    def __init__(self):
        self.log_area = st.empty()
        
    def get_real_trade_dates(self, count=3):
        """修复版：解决 .dt 报错，实现跨假期/周末的真实日期回溯"""
        try:
            # 获取上证指数日线作为真实交易日历锚点
            df = ak.stock_zh_index_daily(symbol="sh000001")
            if df is None or df.empty: return []
            
            # 统一强制转换，避开 pandas 版本导致的 .dt 异常
            df['date'] = pd.to_datetime(df['date'])
            all_valid_dates = df['date'].dt.strftime("%Y%m%d").tolist()
            
            # 获取最近的 N 个真实交易日并降序 [本日(T), 昨日(T-1), 前日(T-2)]
            return all_valid_dates[-count:][::-1]
        except Exception as e:
            st.error(f"日期回溯引擎故障: {e}")
            return []

    def session_audit(self, df_tick):
        """核心审计：穿透早尾盘双窗口，识别『冰山算法』与『机构拆单』"""
        if df_tick is None or df_tick.empty: return 0, "无数据"
        
        # 预处理时间列
        df_tick['time_dt'] = pd.to_datetime(df_tick['time'], format='%H:%M:%S', errors='coerce')
        
        # 投行级双窗口定义
        m_limit = datetime.strptime("10:30:00", "%H:%M:%S").time()
        a_limit = datetime.strptime("14:00:00", "%H:%M:%S").time()
        
        morning_wave = df_tick[df_tick['time_dt'].dt.time <= m_limit]
        afternoon_wave = df_tick[df_tick['time_dt'].dt.time >= a_limit]
        
        def calculate_score(sub_df):
            if sub_df.empty or len(sub_df) < 15: return 0
            
            # 因子审计：价格标准差(静默度)、中性占比(机构指纹)
            p_std = sub_df['price'].astype(float).std()
            n_ratio = len(sub_df[sub_df['type']=='中性']) / len(sub_df)
            
            score = 0
            if p_std < 0.010: score += 2    # 极度静默：主力控盘标志
            if n_ratio > 0.32: score += 2   # 强中性占比：典型冰山建仓
            if len(sub_df[sub_df['成交额'] > 180000]) < 6: score += 1 # 细碎拆单：隐蔽性审计
            return score

        ms = calculate_score(morning_wave)
        as_score = calculate_score(afternoon_wave)
        
        return (ms, "早") if ms >= as_score else (as_score, "尾")

# =================== 3. UI 与 全自动执行 ===================
st.set_page_config(page_title="Sniffer Pro V6.1", layout="wide")
st.title("🏛️ Sniffer Pro 投行全时段审计台")
st.info("💡 模式：跨时序回溯。本日/昨日/前日【独立打分对齐】，支持非交易日深度复盘。")

sniffer = InstitutionalSniffer()
dates = sniffer.get_real_trade_dates(3)

if not dates:
    st.error("❌ 无法锚定交易时序，请检查网络或数据源。")
    st.stop()

# 侧边栏：时序概览
st.sidebar.header("🗓️ 物理交易日序列")
labels = ["本日", "昨日", "前日"]
for i, d in enumerate(dates):
    st.sidebar.metric(labels[i], d)

if st.sidebar.button("🚀 启动全自动深度审计/复盘", use_container_width=True):
    while True:
        # Step 1: 捕捉最近一笔有效的主力资金流向作为池子
        sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")
        if sectors is not None:
            target_sectors = sectors.head(5)
            all_results = []
            
            for _, s_row in target_sectors.iterrows():
                sniffer.log_area.warning(f"🔍 穿透审计中：{s_row['名称']} 板块...")
                stocks = robust_request(ak.stock_board_industry_cons_em, symbol=s_row['名称'])
                
                if stocks is not None:
                    # 每板块扫描前 6 只核心权重股
                    for _, st_row in stocks.head(6).iterrows():
                        code = st_row['代码']
                        f_code = f"{'sh' if code.startswith('6') else 'sz'}{code}"
                        
                        res = {"名称": st_row['名称'], "代码": code, "板块": s_row['名称']}
                        
                        # 依次回溯这三个特定的物理交易日
                        for i, date in enumerate(dates):
                            label = labels[i]
                            df_tick = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
                            score, session = sniffer.session_audit(df_tick)
                            res[f"{label}评分"] = score
                            res[f"{label}时段"] = session
                            time.sleep(0.5) # 避开接口频率限制
                        
                        all_results.append(res)

            if all_results:
                df_final = pd.DataFrame(all_results)
                cols_order = ["名称", "本日评分", "本日时段", "昨日评分", "昨日时段", "前日评分", "前日时段", "板块", "代码"]
                
                st.subheader(f"📊 跨日算法看板 (更新: {datetime.now().strftime('%H:%M:%S')})")
                
                # 视觉优化：高分绿，低分红
                styled_df = df_final[cols_order].style.background_gradient(
                    cmap='RdYlGn', subset=['本日评分','昨日评分','前日评分']
                )
                
                st.dataframe(styled_df, use_container_width=True)
                st.toast("最新审计报告已送达", icon="✅")
            
        time.sleep(600) # 10分钟轮询一次
        st.rerun()
