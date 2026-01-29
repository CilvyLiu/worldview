import streamlit as st
import pandas as pd
import numpy as np
import io

# =================== 1. 数据清洗引擎 (适配东财多级表头) ===================

def clean_em_data(raw_text, mode="sector"):
    """
    清洗东财原始数据：自动处理‘万/亿/%’，提取核心列
    """
    try:
        # 1. 将粘贴的文本转为 DataFrame，自动处理空格/制表符
        df = pd.read_csv(io.StringIO(raw_text), sep=r'\s+', header=None, on_bad_lines='skip')
        
        # 2. 通用数值清洗函数
        def to_num(s):
            s = str(s).replace('%', '').replace('万', '').replace('亿', '').replace(',', '')
            return pd.to_numeric(s, errors='coerce')

        if mode == "sector":
            # 东财板块表解析 (适配你给的表头顺序)
            # 索引映射：名称(1), 今日涨幅(4), 今日主力净占比(12)
            processed = pd.DataFrame()
            processed['名称'] = df.iloc[:, 1]
            processed['今日涨幅'] = df.iloc[:, 4].apply(to_num)
            processed['主力占比'] = df.iloc[:, 12].apply(to_num)
            return processed.dropna(subset=['名称'])
        else:
            # 东财个股(今日/5日/10日)表解析
            # 索引映射：名称(2), 涨跌幅(5), 主力净额(6), 振幅(自查：通常不在资金流主表，建议手动补录或适配)
            # 注意：东财资金流详情表默认不含“振幅”，此处默认补位，建议粘贴时包含振幅列
            processed = pd.DataFrame()
            processed['名称'] = df.iloc[:, 2]
            processed['今日主力'] = df.iloc[:, 6].apply(to_num)
            processed['5日主力'] = df.iloc[:, 6].apply(to_num) # 逻辑见下文说明
            processed['10日主力'] = df.iloc[:, 6].apply(to_num)
            processed['成交量'] = df.iloc[:, 6].apply(to_num) # 占位
            processed['振幅'] = 1.0 # 占位平滑
            return processed.dropna(subset=['名称'])
    except Exception as e:
        st.error(f"解析失败，请确保粘贴了完整的整行数据。错误: {e}")
        return pd.DataFrame()

# =================== 2. 投行算法内核 (禁止删减) ===================

def run_sniffer_audit(df, mode="stock"):
    # 确保数值格式正确
    cols_to_fix = [c for c in df.columns if c != '名称']
    for col in cols_to_fix:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if mode == "sector":
        # First: L-H 象限确认
        df['L-H预警'] = (df['主力占比'] > 3.0) & (df['今日涨幅'] < 2.0)
        return df.sort_values(by='主力占比', ascending=False)
    
    else:
        # Next: 穿透审计
        # 1. Ea 吸筹效率
        df['Ea'] = df['今日主力'] / (df['成交量'] * (df['振幅'] + 0.1))
        # 2. Sm 持仓稳定性 (权重：0.5, 0.3, 0.2)
        df['weighted_sum'] = df['今日主力']*0.5 + df['5日主力']*0.3 + df['10日主力']*0.2
        df['std_flow'] = df.apply(lambda x: np.std([x['今日主力'], x['5日主力'], x['10日主力']]), axis=1)
        df['Sm'] = df['weighted_sum'] / (df['std_flow'] + 1)
        # 3. Signal 爆发点识别
        df['Signal'] = (df['今日主力'] > 0) & (df['5日主力'] < 0) & (df['10日主力'] < 0)
        return df.sort_values(by='Ea', ascending=False)

# =================== 3. UI 界面设计 ===================

st.set_page_config(page_title="Sniffer 嗅嗅 Audit Terminal", layout="wide")
st.title("🏛️ Sniffer 嗅嗅 - 投行数据审计终端")

# --- Step 1: 板块初筛 ---
st.header("Step 1: First - 板块 L-H 象限确认")
sector_input = st.text_area("📋 粘贴东财板块一日行情数据 (整行粘贴)", height=150)

if sector_input:
    sec_base = clean_em_data(sector_input, mode="sector")
    if not sec_base.empty:
        sec_res = run_sniffer_audit(sec_base, mode="sector")
        st.dataframe(sec_res.style.applymap(lambda x: 'background-color: #d4edda' if x == True else '', subset=['L-H预警']), use_container_width=True)

# --- Step 2: 个股三周期审计 ---
st.divider()
st.header("Step 2: Next - 个股多周期穿透")
st.info("💡 请分别粘贴东财个股‘今日’、‘5日’、‘10日’的资金流排行榜数据。")

c1, c2, c3 = st.columns(3)
with c1: in_t = st.text_area("1. 粘贴今日资金流", height=150)
with c2: in_5 = st.text_area("2. 粘贴5日资金流", height=150)
with c3: in_10 = st.text_area("3. 粘贴10日资金流", height=150)

if in_t and in_5 and in_10:
    df_t = clean_em_data(in_t, mode="stock").rename(columns={'今日主力':'主力T'})
    df_5 = clean_em_data(in_5, mode="stock").rename(columns={'今日主力':'主力5'})
    df_10 = clean_em_data(in_10, mode="stock").rename(columns={'今日主力':'主力10'})
    
    # 自动对齐名称合并
    try:
        m = pd.merge(df_t[['名称', '主力T']], df_5[['名称', '主力5']], on='名称')
        m = pd.merge(m, df_10[['名称', '主力10']], on='名称')
        m.columns = ['名称', '今日主力', '5日主力', '10日主力']
        # 补齐计算所需的成交量与振幅 (默认为1进行平滑，建议根据需求微调)
        m['成交量'] = 10000 
        m['振幅'] = 2.0
        
        st_res = run_sniffer_audit(m, mode="stock")
        st.dataframe(st_res[['名称', 'Ea', 'Sm', 'Signal']], use_container_width=True)
        
        targets = st_res[st_res['Signal'] == True]['名称'].tolist()
        if targets:
            st.success(f"🎯 爆发点确认：{', '.join(targets)} 符合审计逻辑")
            st.warning("⚠️ Finally: 请配合 15分钟K线 缩量上涨进行最后确权")
    except Exception as e:
        st.error(f"合并审计失败，请确保三个时间段的股票列表有交集。{e}")
