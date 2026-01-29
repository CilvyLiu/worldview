import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime

# =================== 1. 底层请求引擎 ===================
def robust_request(func, *args, **kwargs):
    """对抗断连的弹性引擎"""
    retries = 3
    for i in range(retries):
        try:
            res = func(*args, **kwargs)
            if res is not None: return res
        except:
            time.sleep(2)
    return None

# =================== 2. 审计核心类 ===================
class InstitutionalSniffer:
    def __init__(self):
        self.log_area = st.empty()
        
    def get_real_trade_dates(self, count=3):
        """修复版：通过指数行情获取真实交易日，规避日历接口失效"""
        try:
            # 获取上证指数日线，这是最稳定的交易日来源
            df = ak.stock_zh_index_daily(symbol="sh000001")
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except Exception as e:
            st.error(f"日期引擎启动失败: {e}")
            return []

    def session_audit(self, df_tick):
        """双窗口算法审计：早盘脉冲 vs 尾盘冰山"""
        if df_tick is None or df_tick.empty: return 0, "无"
        
        df_tick['time_dt'] = pd.to_datetime(df_tick['time'], format='%H:%M:%S', errors='coerce')
        
        # 投行审计窗口定义
        morning_wave = df_tick[df_tick['time_dt'].dt.time <= datetime.strptime("10:30:00", "%H:%M:%S").time()]
        afternoon_wave = df_tick[df_tick['time_dt'].dt.time >= datetime.strptime("14:00:00", "%H:%M:%S").time()]
        
        def calculate_score(sub_df):
            if sub_df.empty or len(sub_df) < 15: return 0
            
            # 因子：中性占比（机构冰山）、价格标准差（受控度）、单笔均量
            p_std = sub_df['price'].astype(float).std()
            n_ratio = len(sub_df[sub_df['type']=='中性']) / len(sub_df)
            
            score = 0
            if p_std < 0.010: score += 2    # 极度控盘（静默）
            if n_ratio > 0.32: score += 2   # 强机构指纹（冰山）
            if len(sub_df[sub_df['成交额'] > 180000]) < 6: score += 1 # 拆单审计
            return score

        m_score = calculate_score(morning_wave)
        a_score = calculate_score(afternoon_wave)
        
        return (m_score, "早") if m_score >= a_score else (a_score, "尾")

# =================== 3. UI 与 执行 ===================
st.set_page_config(page_title="Sniffer Pro V5.0", layout="wide")
st.title("🏛️ Sniffer Pro 投行双窗口审计台")
st.info("💡 核心逻辑：本日/昨日/前日【分项对齐】+ 跨时区早尾盘【算法特征捕捉】")

sniffer = InstitutionalSniffer()
dates = sniffer.get_real_trade_dates(3)

if not dates:
    st.error("无法确定交易日期，系统挂起。")
    st.stop()

# 侧边栏：时序概览
st.sidebar.header("🗓️ 审计时序锚点")
for i, d in enumerate(dates):
    label = ["本日", "昨日", "前日"][i]
    st.sidebar.metric(label, d)

if st.sidebar.button("🚀 启动全自动深度审计", use_container_width=True):
    while True:
        # Step 1: 捕捉今日强势流向板块
        sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")
        if sectors is not None:
            target_sectors = sectors.head(5)
            all_results = []
            
            for _, s_row in target_sectors.iterrows():
                sniffer.log_area.warning(f"正在穿透审计：{s_row['名称']} 板块...")
                stocks = robust_request(ak.stock_board_industry_cons_em, symbol=s_row['名称'])
                
                if stocks is not None:
                    # 每板块扫描前 8 只高权成分股
                    for _, st_row in stocks.head(8).iterrows():
                        code = st_row['代码']
                        f_code = f"sh{code}" if code.startswith('6') else f"sz{code}"
                        
                        row_data = {"名称": st_row['名称'], "代码": code, "板块": s_row['名称']}
                        
                        # 倒查 3 个交易日
                        for i, date in enumerate(dates):
                            label = ["本日", "昨日", "前日"][i]
                            df_tick = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
                            
                            score, session = sniffer.session_audit(df_tick)
                            row_data[f"{label}评分"] = score
                            row_data[f"{label}时段"] = session
                            time.sleep(0.4) # 频率保护
                        
                        all_results.append(row_data)

            if all_results:
                df_res = pd.DataFrame(all_results)
                # 重新排列列顺序，让数据更 scannable
                cols_order = ["名称", "本日评分", "本日时段", "昨日评分", "昨日时段", "前日评分", "前日时段", "板块", "代码"]
                
                st.subheader(f"📊 跨日算法审计看板 ({datetime.now().strftime('%H:%M:%S')})")
                
                # 动态高亮
                styled_df = df_res[cols_order].style.background_gradient(
                    cmap='RdYlGn', subset=['本日评分','昨日评分','前日评分']
                ).format(precision=1)
                
                st.dataframe(styled_df, use_container_width=True)
                st.toast("新一轮审计数据已同步", icon="✅")
            
        sniffer.log_area.info(f"等待下一轮扫描... (Next: {datetime.now().replace(minute=(datetime.now().minute+10)%60).strftime('%H:%M')})")
        time.sleep(600)
        st.rerun()
