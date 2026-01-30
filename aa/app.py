import streamlit as st
import pandas as pd
import numpy as np
import re

# ================= 页面配置 =================
st.set_page_config(page_title="嗅嗅 Sniffer - 扫货雷达", layout="wide")

# ================= 数据清洗核心 =================
def clean_val(val):
    """统一清洗数字、百分比、亿/万等格式，识别东财噪音"""
    if pd.isna(val) or val in ['-', '数据', '']:
        return 0.0
    # 移除所有杂质字符
    val = str(val).replace(' ', '').replace(',', '').replace('详情', '').replace('股吧', '')
    mult = 1.0
    if '亿' in val:
        mult = 1e8
        val = val.replace('亿','')
    elif '万' in val:
        mult = 1e4
        val = val.replace('万','')
    if '%' in val:
        mult *= 0.01
        val = val.replace('%','')
    try:
        return float(val) * mult
    except:
        return 0.0

# ================= 强力正则解析 =================
def parse_smart(text, mode="sector"):
    """针对粘连格式的正则解析引擎"""
    lines = text.strip().split('\n')
    data = []
    
    if mode == "sector":
        # 匹配：序号 + 名称 + 涨跌幅% + 资金(万/亿) + 净占比%
        pattern = re.compile(r'(\d+)\s*([\u4e00-\u9fa5]+).*?(-?\d+\.?\d*%).*?(-?\d+\.?\d*[万亿]).*?(-?\d+\.?\d*%)')
    else:
        # 匹配：序号 + 6位代码 + 名称 + 价格 + 涨跌幅% + 资金(万/亿)
        pattern = re.compile(r'(\d+)\s*(\d{6})\s*([\u4e00-\u9fa5\s]+).*?(\d+\.\d+)\s*(-?\d+\.?\d*%).*?(-?\d+\.?\d*[万亿])')

    for line in lines:
        match = pattern.search(line)
        if match:
            data.append(match.groups())
    return data

# ================= UI 界面 =================
st.title("🕵️ 嗅嗅 Sniffer - 低价扫货识别器")
st.markdown(f"> **Nova，当前策略：First (板块) -> Next (个股) -> Finally (伏击)**")

col1, col2 = st.columns(2)

with col1:
    st.subheader("第一步：初筛板块 (First)")
    sector_raw = st.text_area("粘贴板块流向数据", height=250, placeholder="支持粘连格式，如：1通信设备股吧0.21%20.28亿...")

with col2:
    st.subheader("第二步：穿透个股 (Next)")
    stock_raw = st.text_area("粘贴个股资金数据", height=250, placeholder="支持粘连格式，如：1002041登海种业11.2910.04%2.26亿...")

# ================= 执行逻辑 =================
if st.button("🚀 开始执行智能嗅探"):
    # --- 板块逻辑 ---
    if sector_raw:
        sec_rows = parse_smart(sector_raw, "sector")
        if sec_rows:
            df_sec = pd.DataFrame(sec_rows, columns=['序号', '名称', '涨跌幅', '主力净额', '净占比'])
            for c in ['涨跌幅','主力净额','净占比']: df_sec[c] = df_sec[c].apply(clean_val)
            
            st.write("### 📊 板块初筛结果")
            # 标记建议穿透的板块（资金流入大但涨幅小的“捂盖子”板块）
            df_sec['穿透建议'] = df_sec.apply(lambda r: "🎯 重点去搜" if r['主力净额'] > 0 and r['涨跌幅'] < 0.015 else "观察", axis=1)
            st.dataframe(df_sec.sort_values(by='主力净额', ascending=False), use_container_width=True)
        else:
            st.warning("板块解析失败，请检查是否包含序号、名称、百分比及金额。")

    # --- 个股逻辑 ---
    if stock_raw:
        stk_rows = parse_smart(stock_raw, "stock")
        if stk_rows:
            # 提取正则匹配的列
            df_stk = pd.DataFrame(stk_rows, columns=['序号', '代码', '名称', '价格', '涨跌幅', '今日净额'])
            for c in ['价格','涨跌幅','今日净额']: df_stk[c] = df_stk[c].apply(clean_val)

            # --- Ea 因子与信号判断 ---
            df_stk['Ea'] = df_stk['今日净额'] / (df_stk['涨跌幅'].abs() + 0.01)
            df_stk['建议动作'] = "等待信号"
            
            # 1. 💎 极品背离：资金入，股价跌
            df_stk.loc[(df_stk['今日净额'] > 0) & (df_stk['涨跌幅'] < 0), '建议动作'] = "💎 极品背离 (主力压盘)"
            # 2. 🎯 低价扫货：资金入，股价横盘 (-1.5% 到 1.5%)
            df_stk.loc[(df_stk['今日净额'] > 0) & (df_stk['涨跌幅'].between(-0.015, 0.015)) & (df_stk['建议动作']=="等待信号"), '建议动作'] = "🎯 低价扫货 (爆发临界)"

            st.divider()
            st.subheader("💰 Finally: 最终伏击清单")
            best = df_stk[df_stk['建议动作'].str.contains("💎|🎯")].sort_values(by='Ea', ascending=False)
            
            def style_action(val):
                if "💎" in val: return 'background-color: #8b0000; color: white'
                if "🎯" in val: return 'background-color: #006400; color: white'
                return ''

            st.dataframe(best.style.applymap(style_action, subset=['建议动作']), use_container_width=True)
        else:
            st.error("个股数据缺失或解析失败！请确保粘贴了带有代码、价格和净额的个股列表。")

st.markdown("""
---
### Nova 的操作说明：
1. **First (板块)**：贴入东财板块流向，寻找**主力净额**为正，但**涨跌幅**很小的板块。
2. **Next (个股)**：点进选中的板块，把个股流向（今日/5日/10日均可）贴进右框。
3. **Finally (确权)**：系统锁定 $E_a$ 因子（吸筹效率系数）极高的个股，那便是伏击点。
""")
