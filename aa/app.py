import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime

# =================== 1. 弹性请求引擎 ===================
def robust_request(func, *args, **kwargs):
    """对抗频率限制：加入随机扰动并支持多轮重试"""
    for i in range(3):
        try:
            # 随机延迟，模拟真人操作，降低封锁概率
            time.sleep(random.uniform(0.5, 1.5))
            res = func(*args, **kwargs)
            if res is not None and not (isinstance(res, pd.DataFrame) and res.empty): 
                return res
        except Exception:
            if i == 2: st.warning(f"接口 {func.__name__} 响应超时，尝试切换数据源...")
            time.sleep(2)
    return None

# =================== 2. 反冰山审计引擎 ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        """核心：通过指数日线确保获取的是真实的交易日期"""
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df['date'] = pd.to_datetime(df['date'])
            # 返回降序排列的最近交易日 [本日, 昨日, 前日]
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except: return []

    def anti_iceberg_audit(self, df_tick):
        """反冰山算法：审计静默扫货指纹"""
        if df_tick is None or df_tick.empty: return 0, "无数据"
        
        # 强制数值化清洗，解决 TypeError 的核心防线
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        
        # 1. 中性盘占比
        neutral_df = df_tick[df_tick['type'] == '中性']
        n_ratio = len(neutral_df) / len(df_tick) if len(df_tick) > 0 else 0
        
        # 2. 价格波动极差 (冰山单通常在极窄区间成交)
        p_std = df_tick['price'].std()
        
        # 3. 小额拆单指纹
        small_neutral_count = len(neutral_df[neutral_df['成交额'] < 50000])
        
        score = 0
        if n_ratio > 0.35: score += 2    
        if p_std is not None and p_std < 0.008: score += 2  
        if len(neutral_df) > 0 and small_neutral_count > len(neutral_df) * 0.7: score += 1 
        
        intensity = "极高" if score >= 4 else ("高" if score >= 3 else "弱")
        return score, intensity

# =================== 3. 决策工作台 UI ===================
st.set_page_config(page_title="Sniffer Pro V7.7", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)

st.title("🏛️ Sniffer Pro 投行决策工作台")

if not dates:
    st.error("🚨 无法获取交易日历，请检查网络或更换 IP 环境。")
    st.stop()

# --- 日期展示区：侧边栏锚点 ---
st.sidebar.header("🗓️ 审计交易日锚点")
labels = ["本日", "昨日", "前日"]
for i, d in enumerate(dates):
    st.sidebar.metric(f"{labels[i]} (T-{i})", d)

# --- 第一步：板块异常监测 (多源冗余) ---
st.header("Step 1: 捕捉【静默流入】异常板块")
with st.status("正在执行多源数据对冲扫描...", expanded=True) as status:
    # 尝试路径 A: 行业板块
    df_sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")
    
    # 路径 A 失败则启用 路径 B: 概念板块
    if df_sectors is None:
        df_sectors = robust_request(ak.stock_concept_fund_flow_em, indicator="今日")

    if df_sectors is not None:
        # 统一字段名（不同接口返回头可能不一致）
        df_sectors.columns = [c.replace('今日', '').replace('涨跌幅', '今日涨跌幅') for c in df_sectors.columns]
        
        # 关键修复：强制数值化并填充
        df_sectors['今日涨跌幅'] = pd.to_numeric(df_sectors['今日涨跌幅'], errors='coerce').fillna(0)
        df_sectors['主力净流入-净占比'] = pd.to_numeric(df_sectors['主力净流入-净占比'], errors='coerce').fillna(0)
        
        # 筛选逻辑：涨幅温和且资金净占比靠前
        target_sectors = df_sectors[
            (df_sectors['今日涨跌幅'] > 0.5) & (df_sectors['今日涨跌幅'] < 4.0)
        ].sort_values('主力净流入-净占比', ascending=False).head(10)
        
        if target_sectors.empty:
            st.warning("触发异常行情修正：当前板块普遍过热，已放宽阈值。")
            target_sectors = df_sectors[df_sectors['今日涨跌幅'] < 6.0].sort_values('主力净流入-净占比', ascending=False).head(10)
        
        status.update(label="数据源同步成功", state="complete")
        st.dataframe(target_sectors[['名称', '主力净流入-净占比', '今日涨跌幅']], use_container_width=True)
    else:
        status.update(label="API 访问受限", state="error")
        st.error("所有板块接口请求均被封锁。建议更换代理或稍后再试。")
        st.stop()

# --- 第二步：个股筛选 ---
st.divider()
st.header("Step 2: 穿透精选个股 (反过热筛选)")
selected_sector = st.selectbox("请选定一个板块进行穿透：", ["请选择"] + target_sectors['名称'].tolist())

if selected_sector != "请选择":
    with st.spinner(f"正在穿透 {selected_sector} 成员..."):
        all_stocks = robust_request(ak.stock_board_industry_cons_em, symbol=selected_sector)
        
        if all_stocks is not None:
            all_stocks['涨跌幅'] = pd.to_numeric(all_stocks['涨跌幅'], errors='coerce').fillna(0)
            all_stocks['换手率'] = pd.to_numeric(all_stocks['换手率'], errors='coerce').fillna(0)
            
            # 过滤掉涨幅过大和换手异常的标的
            quality_stocks = all_stocks[
                (all_stocks['涨跌幅'] < 5.0) & (all_stocks['涨跌幅'] > -1.5) & (all_stocks['换手率'] < 10.0)
            ].sort_values('换手率', ascending=False).head(15)
            
            st.subheader(f"📍 {selected_sector} - 审计候选名单")
            selected_stocks = st.multiselect("请勾选需要执行审计的个股：", 
                                             quality_stocks['名称'].tolist(), 
                                             default=quality_stocks['名称'].tolist()[:3])
            
            # --- 第三步：跨时序审计 ---
            if selected_stocks:
                st.divider()
                st.header("Step 3: 三日跨时序【反冰山审计】报告")
                final_data = []
                progress_bar = st.progress(0)
                
                for idx, s_name in enumerate(selected_stocks):
                    s_row = quality_stocks[quality_stocks['名称'] == s_name].iloc[0]
                    code = s_row['代码']
                    f_code = f"{'sh' if str(code).startswith('6') else 'sz'}{code}"
                    report = {"名称": s_name, "代码": code, "当前涨幅": s_row['涨跌幅']}
                    
                    for i, date in enumerate(dates):
                        label = labels[i]
                        # 163 接口相对稳定
                        df_tick = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
                        score, intensity = sniffer.anti_iceberg_audit(df_tick)
                        report[f"{label}评分"] = score
                        report[f"{label}特征"] = intensity
                        time.sleep(0.4)
                    
                    final_data.append(report)
                    progress_bar.progress((idx + 1) / len(selected_stocks))
                
                df_report = pd.DataFrame(final_data)
                st.dataframe(
                    df_report.style.background_gradient(cmap='RdYlGn', subset=[f"{l}评分" for l in labels]),
                    use_container_width=True
                )
                st.success(f"✅ 审计完成。基准日期：{', '.join(dates)}")

st.sidebar.caption(f"系统运行中 | {datetime.now().strftime('%H:%M:%S')}")
