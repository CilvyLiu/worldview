import streamlit as st
import pandas as pd
import numpy as np
import io

# =================== 1. 投行公式计算核心 (公式 1:1 还原) ===================

def run_sniffer_audit(df, mode="stock"):
    # 强制数值化处理
    for col in df.columns:
        if col not in ['名称', '代码', '审计判语']:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
    
    if mode == "sector":
        # First: 空间坐标定位（板块初筛）
        # 逻辑：板块占比 > 3% 且 涨幅 < 2% 为“疑似静默扫货区”
        df['L-H预警'] = (df['主力占比'] > 3.0) & (df['今日涨幅'] < 2.0)
        return df.sort_values(by='主力占比', ascending=False)
    
    else:
        # Next: 个股审计公式还原
        
        # 1. Ea = 今日主力净额 / (成交量 * 振幅)
        # 振幅加 0.1 平滑项防止除零，同时捕捉“极小范围波动”的静默特征
        df['Ea'] = df['今日主力'] / (df['成交量'] * (df['振幅'] + 0.1))
        
        # 2. Sm = Σ(Inflow_t * w_t) / σ(Inflow)
        # w_t 时间衰减权重设定：今日 0.5, 5日 0.3, 10日 0.2
        df['weighted_sum'] = df['今日主力']*0.5 + df['5日主力']*0.3 + df['10日主力']*0.2
        # 计算资金流标准差 σ (NetInflow)
        df['std_flow'] = df.apply(lambda x: np.std([x['今日主力'], x['5日主力'], x['10日主力']]), axis=1)
        df['Sm'] = df['weighted_sum'] / (df['std_flow'] + 1)
        
        # 3. Signal = (Today > 0) ∩ (5D < 0) ∩ (10D < 0)
        # 含义：过去10天/5天在流出洗盘，今天突然反转流入，确认爆发点
        df['Signal'] = (df['今日主力'] > 0) & (df['5日主力'] < 0) & (df['10日主力'] < 0)
        
        return df.sort_values(by='Ea', ascending=False)

# =================== 2. UI 界面设计 ===================

st.set_page_config(page_title="Sniffer 嗅嗅 Audit Terminal", layout="wide")
st.title("🏛️ Sniffer 嗅嗅 - 投行数据审计终端")
st.caption("系统逻辑：寻找资金流向与价格波动的‘非线性背离’")

# --- Step 1: 板块数据输入 (First) ---
st.header("Step 1: First - 板块 L-H 象限确认")
st.markdown("💡 **操作指南**：粘贴板块列表（名称 | 今日涨幅 | 主力占比），筛选占比 > 3% 且 涨幅 < 2% 的目标。")

sector_input = st.text_area("📋 粘贴板块数据", height=150, placeholder="软件开发 1.2 4.5\n医疗服务 -0.5 3.8")

if sector_input:
    # 支持空格或制表符分隔
    sec_df = pd.read_csv(io.StringIO(sector_input), sep=r'\s+', names=['名称', '今日涨幅', '主力占比'])
    sec_res = run_sniffer_audit(sec_df, mode="sector")
    
    st.write("🚩 板块审计结果 (绿色为 L-H 扫货预警区)：")
    st.dataframe(sec_res.style.applymap(lambda x: 'background-color: #d4edda; color: #155724' if x == True else '', subset=['L-H预警']), use_container_width=True)

# --- Step 2: 个股数据输入 (Next) ---
st.divider()
st.header("Step 2: Next - 个股 5日/10日 穿透审计")
st.markdown("💡 **操作指南**：在目标板块中复制个股数据（名称 | 今日主力 | 5日主力 | 10日主力 | 成交量 | 振幅）。")

stock_input = st.text_area("📋 粘贴个股数据", height=200, placeholder="股票A 5000 -2000 -8000 100000 2.5")

if stock_input:
    st.info("💡 正在执行 Sniffer $E_a$ & $S_m$ 双重审计逻辑...")
    st_df = pd.read_csv(io.StringIO(stock_input), sep=r'\s+', 
                        names=['名称', '今日主力', '5日主力', '10日主力', '成交量', '振幅'])
    st_res = run_sniffer_audit(st_df, mode="stock")
    
    # 展示核心审计指标
    st.dataframe(st_res[['名称', 'Ea', 'Sm', 'Signal']], use_container_width=True)
    
    # 确权提醒
    targets = st_res[st_res['Signal'] == True]
    if not targets.empty:
        st.success(f"🎯 爆发点确认：{', '.join(targets['名称'].tolist())} 符合 (Today+) ∩ (5D-) ∩ (10D-) 反转逻辑")
        st.warning("⚠️ Finally: 请手动配合 15分钟K线 缩量上涨进行最后确权")
