import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# =================== 1. 强力数据清洗引擎 (适配东财长数值与详情页) ===================

def to_num(s):
    """极致兼容：处理千分位、负号、百分号、单位、以及长浮点数"""
    if pd.isna(s): return 0.0
    s = str(s).strip().replace(',', '').replace('%', '')
    # 提取数字、负号和小数点
    match = re.search(r'[-+]?\d*\.?\d+', s)
    if not match: return 0.0
    
    val = float(match.group())
    if '亿' in s: val *= 1e8
    if '万' in s: val *= 1e4
    return val

def clean_em_data(raw_text, mode="stock"):
    """
    智能兼容东财主力榜和详情页格式
    mode: 'sector' 板块, 'stock' 个股
    """
    try:
        lines = [line.strip() for line in raw_text.strip().split('\n') if line.strip()]
        # 跳过标题行（含中文关键字）
        lines = [l for l in lines if not re.search(r'名称|代码|涨幅|主力|占比', l)]
        data = [re.split(r'\s+', line) for line in lines]
        df = pd.DataFrame(data)

        if df.empty:
            return pd.DataFrame()

        if mode == "sector":
            processed = pd.DataFrame()
            # 名称列：首个中文字符
            def find_name(row):
                for item in row:
                    if re.search(r'[\u4e00-\u9fa5]', str(item)):
                        return item
                return "未知"
            processed['名称'] = df.apply(find_name, axis=1)

            # 涨幅列：找含 % 或数字的小数
            processed['今日涨幅'] = df.apply(
                lambda r: next((to_num(x) for x in r if '%' in str(x) or re.match(r'[-+]?\d*\.?\d+', str(x))), 0), axis=1
            )

            # 主力占比列：找含 % 或单位列
            processed['主力占比'] = df.apply(
                lambda r: next((to_num(x) for x in r if re.search(r'[\d\.]+[%亿万]', str(x))), 0), axis=1
            )
            return processed[processed['名称'] != "未知"]

        else:  # stock 个股
            processed = pd.DataFrame()
            # 尝试自动定位代码（数字 + 可选前缀）
            processed['代码'] = df.apply(
                lambda r: next((str(x) for x in r if re.match(r'\d{6}', str(x))), '000000'), axis=1
            )
            # 名称列：首个中文字符
            processed['名称'] = df.apply(
                lambda r: next((x for x in r if re.search(r'[\u4e00-\u9fa5]', str(x))), '未知'), axis=1
            )
            # 主力净额：找含数字或亿万的列
            processed['主力净额'] = df.apply(
                lambda r: next((to_num(x) for x in r if re.search(r'[-+]?\d*\.?\d+[亿万]?', str(x))), 0), axis=1
            )
            return processed[processed['名称'] != "未知"]

    except Exception as e:
        print("clean_em_data error:", e)
        return pd.DataFrame()

# =================== 2. 投行审计内核 (First -> Next) ===================

def run_sniffer_audit(df, mode="stock"):
    # 数值预处理：排除非数值列
    numeric_cols = [c for c in df.columns if c not in ['名称', '代码', '审计状态', 'is_target']]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if mode == "sector":
        # First: L-H 扫货区审计 (Nova 指令：占比>3%, 涨幅<2%)
        df['审计状态'] = np.where(
            (df['主力占比'] > 3.0) & (df['今日涨幅'] < 2.0), 
            "🚩 重点关注 (L-H扫货区)", 
            "待机"
        )
        return df.sort_values(by='主力占比', ascending=False)
    
    else:
        # Next: 穿透审计 [Ea, Sm, Signal]
        # Ea 吸筹效率
        df['Ea'] = df['今日主力'] / (10000 * 2.1) 
        
        # Sm 持仓稳定性 (权重分配：0.5, 0.3, 0.2)
        df['weighted_sum'] = df['今日主力']*0.5 + df['5日主力']*0.3 + df['10日主力']*0.2
        df['std_flow'] = df.apply(lambda x: np.std([x['今日主力'], x['5日主力'], x['10日主力']]), axis=1)
        df['Sm'] = df['weighted_sum'] / (df['std_flow'] + 1)
        
        # Signal 爆发点识别 (今日流入 + 5日洗盘 + 10日洗盘)
        df['is_target'] = (df['今日主力'] > 0) & (df['5日主力'] < 0) & (df['10_主力'] < 0 if '10_主力' in df else df['10日主力'] < 0)
        
        # 审计状态判语
        def get_label(row):
            if row['is_target']: return "💎 爆发点确认"
            if row['今日主力'] > 0 and row['5日主力'] > 0: return "📈 持续吸筹"
            return "洗盘中"
            
        df['审计状态'] = df.apply(get_label, axis=1)
        return df.sort_values(by='Ea', ascending=False)

# =================== 3. UI 界面设计 (移动端优化) ===================

st.set_page_config(page_title="Sniffer Pro", layout="wide")
st.title("🏛️ Sniffer 嗅嗅 - 投行数据审计终端")

# Step 1: 板块初筛
st.header("Step 1: First")
sector_input = st.text_area("📥 粘贴板块行情全行数据", height=100, placeholder="粘贴此处...")
if st.button("🚀 执行板块审计", use_container_width=True):
    if sector_input:
        res = run_sniffer_audit(clean_em_data(sector_input, mode="sector"), mode="sector")
        if not res.empty:
            st.table(res[['名称', '今日涨幅', '主力占比', '审计状态']])
        else:
            st.warning("未能识别数据，请检查复制内容。")

st.divider()

# Step 2: 个股穿透
st.header("Step 2: Next")
st.caption("提示：依次粘贴板块下个股的 今日/5日/10日 资金榜单")
c1, c2, c3 = st.columns(3)
with c1: in_t = st.text_area("1. 今日资金流", height=120)
with c2: in_5 = st.text_area("2. 5日资金流", height=120)
with c3: in_10 = st.text_area("3. 10日资金流", height=120)

if st.button("🔍 执行个股穿透审计", use_container_width=True):
    if in_t and in_5 and in_10:
        dt = clean_em_data(in_t, mode="stock").rename(columns={'主力净额':'今日主力'})
        d5 = clean_em_data(in_5, mode="stock").rename(columns={'主力净额':'5日主力'})
        d10 = clean_em_data(in_10, mode="stock").rename(columns={'主力净额':'10日主力'})
        
        try:
            # 核心对齐逻辑：多表基于代码和名称合并
            m = pd.merge(dt, d5, on=['代码','名称']).merge(d10, on=['代码','名称'])
            res = run_sniffer_audit(m, mode="stock")
            st.table(res[['名称', '代码', 'Ea', 'Sm', '审计状态']])
            
            # 爆发点提醒
            targets = res[res['审计状态'] == "💎 爆发点确认"]['名称'].tolist()
            if targets:
                st.success(f"🎯 潜伏目标已锁定：{', '.join(targets)}")
                st.warning("⚠️ Finally: 请确认 15 分钟 K 线缩量上涨！")
        except Exception as e:
            st.error("合并失败。请确保三个框粘贴的是同一板块的数据清单。")
