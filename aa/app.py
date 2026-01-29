import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime

# =================== 1. 底层请求引擎 ===================
def robust_request(func, *args, **kwargs):
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
        try:
            trade_df = ak.tool_trade_date_hist_sina()
            today = datetime.now().date()
            valid_dates = trade_df[trade_df['trade_date'] <= today].tail(count)
            return valid_dates['trade_date'].dt.strftime("%Y%m%d").tolist()[::-1]
        except: return []

    def session_audit(self, df_tick):
        """对 Tick 数据进行双窗口（早盘/尾盘）算法审计"""
        df_tick['time_dt'] = pd.to_datetime(df_tick['time'], format='%H:%M:%S', errors='coerce')
        
        # 定义投行审计窗口
        morning_wave = df_tick[df_tick['time_dt'].dt.time <= datetime.strptime("10:30:00", "%H:%M:%S").time()]
        afternoon_wave = df_tick[df_tick['time_dt'].dt.time >= datetime.strptime("14:00:00", "%H:%M:%S").time()]
        
        def calculate_score(sub_df):
            if sub_df.empty or len(sub_df) < 10: return 0
            # 因子：中性占比、价格标准差、成交额集中度
            p_std = sub_df['price'].astype(float).std()
            n_ratio = len(sub_df[sub_df['type']=='中性']) / len(sub_df)
            # 投行级评分 (0-5)
            score = 0
            if p_std < 0.012: score += 2    # 极度静默
            if n_ratio > 0.30: score += 2   # 强冰山特征
            if len(sub_df[sub_df['成交额'] > 200000]) < 5: score += 1 # 拆单精细度
            return score

        m_score = calculate_score(morning_wave)
        a_score = calculate_score(afternoon_wave)
        # 取全天最高价值时段的得分
        return max(m_score, a_score), "早" if m_score >= a_score else "尾"

# =================== 3. UI 与 执行 ===================
st.set_page_config(page_title="Sniffer V5.0", layout="wide")
st.title("🏛️ Sniffer V5.0 投行双窗口全自动扫描")
st.info("💡 逻辑：本日/昨日/前日独立打分 + 早尾盘双窗口扫描。")

sniffer = InstitutionalSniffer()
dates = sniffer.get_real_trade_dates(3)

if not dates:
    st.error("日期获取失败")
    st.stop()

# 侧边栏展示日期
cols = st.sidebar.columns(3)
for i, d in enumerate(dates):
    label = ["本日", "昨日", "前日"][i]
    cols[i].metric(label, d)

if st.sidebar.button("🚀 开启全自动循环审计"):
    while True:
        sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")
        if sectors is not None:
            # 锁定资金流入最强的 5 个板块
            target_sectors = sectors.head(5)
            all_results = []
            
            for _, s_row in target_sectors.iterrows():
                sniffer.log_area.text(f"⏳ 正在审计板块: {s_row['名称']}...")
                stocks = robust_request(ak.stock_board_industry_cons_em, symbol=s_row['名称'])
                
                if stocks is not None:
                    for _, st_row in stocks.head(6).iterrows():
                        f_code = f"sh{st_row['代码']}" if st_row['代码'].startswith('6') else f"sz{st_row['代码']}"
                        
                        row_data = {"名称": st_row['名称'], "代码": st_row['代码'], "板块": s_row['名称']}
                        
                        # 分开审计每一天
                        for i, date in enumerate(dates):
                            df_tick = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
                            if df_tick is not None:
                                score, session = sniffer.session_audit(df_tick)
                                row_data[f"{['本日','昨日','前日'][i]}评分"] = score
                                row_data[f"{['本日','昨日','前日'][i]}时段"] = session
                            else:
                                row_data[f"{['本日','昨日','前日'][i]}评分"] = 0
                            time.sleep(0.6) # 投行级反爬步进
                        
                        all_results.append(row_data)

            if all_results:
                df_res = pd.DataFrame(all_results)
                # 重新排序展示
                cols_order = ["名称", "代码", "板块", "本日评分", "本日时段", "昨日评分", "昨日时段", "前日评分", "前日时段"]
                st.subheader(f"📊 三日独立审计看板 ({datetime.now().strftime('%H:%M:%S')})")
                st.dataframe(df_res[cols_order].style.background_gradient(cmap='RdYlGn', subset=['本日评分','昨日评分','前日评分']), use_container_width=True)
            
        time.sleep(600)
        st.rerun()
