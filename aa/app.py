import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime
import plotly.graph_objects as go

# =================== 1. 弹性请求引擎 ===================
def robust_request(func, *args, **kwargs):
    """对抗频率限制：随机延迟 + 多轮重试"""
    for i in range(3):
        try:
            time.sleep(random.uniform(0.6, 1.3))
            res = func(*args, **kwargs)
            if res is not None and not (isinstance(res, pd.DataFrame) and res.empty):
                return res
        except Exception:
            time.sleep(1.5)
    return None

# =================== 2. 投行级反冰山审计类 ===================
class StrategicSniffer:
    def get_real_trade_dates(self, count=3):
        """精准锚定最近3个真实交易日"""
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df['date'] = pd.to_datetime(df['date'])
            return df['date'].tail(count).dt.strftime("%Y%m%d").tolist()[::-1]
        except:
            return []

    def anti_iceberg_audit(self, df_tick):
        """反冰am算法核心：审计隐藏的静默扫货指纹"""
        if df_tick is None or df_tick.empty: 
            return 0, "无数据"
        
        # 强制数值化清洗，防止比较报错
        df_tick['price'] = pd.to_numeric(df_tick['price'], errors='coerce')
        df_tick['成交额'] = pd.to_numeric(df_tick['成交额'], errors='coerce')
        
        # 1. 识别中性盘成交占比 (Iceberg Ratio)
        neutral_df = df_tick[df_tick['type'] == '中性']
        total_len = len(df_tick)
        n_ratio = len(neutral_df) / total_len if total_len > 0 else 0
        
        # 2. 识别成交价格一致性 (算法控盘指纹)
        p_std = df_tick['price'].std()
        
        # 3. 识别拆单特征 (Frag Index)
        small_neutral_count = len(neutral_df[neutral_df['成交额'] < 50000])
        
        score = 0
        if n_ratio > 0.35: score += 2    # 强中性占比
        if p_std is not None and p_std < 0.008: score += 2  # 极致静默
        if len(neutral_df) > 0 and small_neutral_count > len(neutral_df) * 0.7: 
            score += 1 # 疑似算法拆单
        
        intensity = "极高" if score >= 4 else ("高" if score >= 2 else "弱")
        return score, intensity

# =================== 3. 批量 Tick 获取与审计逻辑 ===================
def batch_tick_request(codes, dates):
    """批量预取 Tick 数据，降低 API 瞬时压力"""
    tick_dict = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, code in enumerate(codes):
        code_str = str(code).zfill(6)
        f_code = f"{'sh' if code_str.startswith('6') else 'sz'}{code_str}"
        tick_dict[code] = {}
        for date in dates:
            status_text.text(f"🚀 嗅探中: {code_str} | 日期: {date}")
            tick_dict[code][date] = robust_request(ak.stock_zh_a_tick_163, symbol=f_code, date=date)
        progress_bar.progress((idx + 1) / len(codes))
    
    status_text.empty()
    return tick_dict

def multi_day_audit(tick_dict, dates, sniffer, name_map):
    """执行跨时序多日审计"""
    reports = []
    for code, day_data in tick_dict.items():
        code_str = str(code).zfill(6)
        report = {"名称": name_map.get(code, "未知"), "代码": code_str}
        for i, date in enumerate(dates):
            df_tick = day_data.get(date)
            score, intensity = sniffer.anti_iceberg_audit(df_tick)
            report[f"T-{i}评分"] = score
            report[f"T-{i}特征"] = intensity
        reports.append(report)
    return pd.DataFrame(reports)

# =================== 4. Streamlit UI 交互 ===================
st.set_page_config(page_title="Sniffer Pro V8", layout="wide")
sniffer = StrategicSniffer()
dates = sniffer.get_real_trade_dates(3)
labels = ["本日", "昨日", "前日"]

st.title("🏛️ Sniffer Pro V8 - 投行级自适应嗅探台")

if not dates:
    st.error("无法获取交易日历，请检查网络或 API 状态")
    st.stop()

# 侧边栏：日期锚点
st.sidebar.header("🗓️ 审计交易日锚点")
for i, d in enumerate(dates):
    st.sidebar.metric(f"{labels[i]} (T-{i})", d)
st.sidebar.caption(f"系统运行时间 | {datetime.now().strftime('%H:%M:%S')}")

# --- Step 1: 板块监测 ---
st.header("Step 1: 捕捉【静默流入】异常板块")
df_sectors = robust_request(ak.stock_sector_fund_flow_rank, indicator="今日")

if df_sectors is not None:
    # 自动清洗字段名以适应不同接口
    df_sectors.columns = [c.replace('今日','').replace('涨跌幅','今日涨跌幅') for c in df_sectors.columns]
    df_sectors['今日涨跌幅'] = pd.to_numeric(df_sectors['今日涨跌幅'], errors='coerce').fillna(0)
    df_sectors['主力净流入-净占比'] = pd.to_numeric(df_sectors['主力净流入-净占比'], errors='coerce').fillna(0)
    
    # 【自动标准】：首选温和放量区 (0.5% - 4.0%)
    target_sectors = df_sectors[(df_sectors['今日涨跌幅'] > 0.5) & (df_sectors['今日涨跌幅'] < 4.0)]
    
    # 如果温和区没鱼，自动调整标准 (自适应异常行情)
    if target_sectors.empty:
        st.warning("行情异常：未发现温和区板块，已自动切换至高强度流入监测。")
        target_sectors = df_sectors.sort_values('主力净流入-净占比', ascending=False).head(10)
    else:
        target_sectors = target_sectors.sort_values('主力净流入-净占比', ascending=False).head(10)
        
    st.dataframe(target_sectors[['名称', '主力净流入-净占比', '今日涨跌幅']], use_container_width=True)
else:
    st.error("板块接口请求失败，请检查 IP 是否被屏蔽")
    st.stop()

# --- Step 2: 个股筛选 ---
st.divider()
st.header("Step 2: 穿透精选个股 (反过热筛选)")
selected_sector = st.selectbox("请选择板块进行审计:", ["请选择"] + target_sectors['名称'].tolist())

if selected_sector != "请选择":
    all_stocks = robust_request(ak.stock_board_industry_cons_em, symbol=selected_sector)
    if all_stocks is not None:
        all_stocks['涨跌幅'] = pd.to_numeric(all_stocks['涨跌幅'], errors='coerce').fillna(0)
        all_stocks['换手率'] = pd.to_numeric(all_stocks['换手率'], errors='coerce').fillna(0)
        
        # 筛选未过热且有流动性的标的
        quality_stocks = all_stocks[
            (all_stocks['涨跌幅'] < 5.0) & (all_stocks['涨跌幅'] > -2.0) & (all_stocks['换手率'] < 10.0)
        ].sort_values('换手率', ascending=False).head(15)
        
        st.subheader(f"📍 {selected_sector} - 审计候选名单")
        selected_stocks = st.multiselect("勾选审计对象：", 
                                         quality_stocks['名称'].tolist(), 
                                         default=quality_stocks['名称'].tolist()[:3])
        
        # --- Step 3: 三日跨时序审计 ---
        if selected_stocks:
            st.divider()
            st.header("Step 3: 三日跨时序【反冰山审计】")
            
            # 准备数据映射
            name_map = quality_stocks.set_index('代码')['名称'].to_dict()
            codes = quality_stocks[quality_stocks['名称'].isin(selected_stocks)]['代码'].tolist()
            
            # 执行批量审计
            tick_dict = batch_tick_request(codes, dates)
            df_report = multi_day_audit(tick_dict, dates, sniffer, name_map)
            
            # 渲染高对比度表格
            score_cols = [f"T-{i}评分" for i in range(len(dates))]
            st.dataframe(
                df_report.style.background_gradient(cmap='RdYlGn', subset=score_cols), 
                use_container_width=True
            )
            st.success(f"✅ 审计完成。基准日期序列：{', '.join(dates)}")

            # --- Step 4: 算法雷达图可视化 ---
            st.divider()
            st.header("Step 4: 高分标的特征雷达图")
            
            # 筛选有算法特征的标的进行可视化
            high_score_df = df_report[df_report[score_cols].max(axis=1) >= 2]
            
            if not high_score_df.empty:
                cols = st.columns(3)
                for idx, (_, row) in enumerate(high_score_df.iterrows()):
                    with cols[idx % 3]:
                        fig = go.Figure()
                        fig.add_trace(go.Scatterpolar(
                            r=[row[f"T-{i}评分"] for i in range(len(dates))],
                            theta=labels,
                            fill='toself',
                            name=row['名称']
                        ))
                        fig.update_layout(
                            polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
                            title=f"{row['名称']} ({row['代码']})",
                            height=350,
                            margin=dict(l=40, r=40, t=60, b=40)
                        )
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("暂未发现具备显著反冰山特征的标的。")
