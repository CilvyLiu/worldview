import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

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
        mult = 10000.0  # 统一转为“万元”
        val = val.replace('亿','')
    elif '万' in val:
        mult = 1.0
        val = val.replace('万','')
    
    is_percent = '%' in val
    if is_percent:
        val = val.replace('%','')
    
    try:
        raw_num = float(val) * mult
        # 如果是百分比，直接返回数值（如 1.07）
        if is_percent:
            return raw_num
        else:
            # 返回万元单位的数值
            return raw_num
    except:
        return 0.0

# ================= 强力正则解析 =================
def parse_smart(text, mode="sector"):
    """针对粘连格式的正则解析引擎"""
    lines = text.strip().split('\n')
    data = []
    
    if mode == "sector":
        pattern = re.compile(r'(\d+)\s*([\u4e00-\u9fa5]+).*?(-?\d+\.?\d*%).*?(-?\d+\.?\d*[万亿]).*?(-?\d+\.?\d*%)')
    else:
        # 适配 Nova 提供的长文本数据流
        pattern = re.compile(r'(\d+)\s+(\d{6})\s+([\u4e00-\u9fa5\w]+)\s+.*?\s+(\d+\.\d+)\s+(-?\d+\.?\d*%?)\s+(-?\d+\.?\d*[万亿]?)')

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
    sector_raw = st.text_area("粘贴板块流向数据", height=200)

with col2:
    st.subheader("第二步：穿透个股 (Next)")
    stock_raw = st.text_area("粘贴个股资金数据", height=200, placeholder="直接粘贴东财个股列表...")

# ================= 执行逻辑 =================
if st.button("🚀 开始执行智能嗅探"):
    # --- 板块逻辑 ---
    if sector_raw:
        sec_rows = parse_smart(sector_raw, "sector")
        if sec_rows:
            df_sec = pd.DataFrame(sec_rows, columns=['序号', '名称', '涨跌幅', '主力净额', '净占比'])
            for c in ['涨跌幅','主力净额','净占比']: df_sec[c] = df_sec[c].apply(clean_val)
            st.write("### 📊 板块初筛结果")
            df_sec['穿透建议'] = df_sec.apply(lambda r: "🎯 重点去搜" if r['主力净额'] > 0 and r['涨跌幅'] < 1.5 else "观察", axis=1)
            st.dataframe(df_sec.sort_values(by='主力净额', ascending=False), use_container_width=True)

    # --- 个股逻辑 ---
    if stock_raw:
        stk_rows = parse_smart(stock_raw, "stock")
        if stk_rows:
            df_stk = pd.DataFrame(stk_rows, columns=['序号', '代码', '名称', '价格', '涨跌幅', '今日净额'])
            
            # 显式转换核心计算列
            df_stk['价格'] = df_stk['价格'].apply(clean_val)
            df_stk['涨跌实数'] = df_stk['涨跌幅'].apply(clean_val)
            df_stk['净流入_万'] = df_stk['今日净额'].apply(clean_val)

            # --- Ea 因子修正计算 ---
            # Ea = 主力万元 / (涨跌绝对值 + 0.1)
            df_stk['Ea'] = df_stk['净流入_万'] / (df_stk['涨跌实数'].abs() + 0.1)
            df_stk['建议动作'] = "观察"
            
            # 1. 💎 极品背离：资金入 > 0，股价跌 < 0
            df_stk.loc[(df_stk['净流入_万'] > 0) & (df_stk['涨跌实数'] < 0), '建议动作'] = "💎 极品背离 (主力压盘)"
            # 2. 🎯 低价扫货：资金入 > 0，股价横盘 (-1.5 到 1.5 之间)
            df_stk.loc[(df_stk['净流入_万'] > 0) & (df_stk['涨跌实数'].between(-1.5, 1.5)) & (df_stk['建议动作']=="观察"), '建议动作'] = "🎯 低价扫货 (爆发临界)"

            st.divider()
            st.subheader("💰 Finally: 最终伏击清单")
            best = df_stk[df_stk['建议动作'].str.contains("💎|🎯")].copy().sort_values(by='Ea', ascending=False)
            
            if not best.empty:
                def style_action(val):
                    if "💎" in val: return 'background-color: #8b0000; color: white'
                    if "🎯" in val: return 'background-color: #006400; color: white'
                    return ''

                display_df = best[['代码', '名称', '价格', '涨跌幅', '今日净额', 'Ea', '建议动作']]
                st.dataframe(display_df.style.applymap(style_action, subset=['建议动作']), use_container_width=True)
                
                # --- 导出功能 ---
                today_str = datetime.now().strftime("%Y%m%d_%H%M")
                csv_data = display_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 导出最终决策清单 (CSV)",
                    data=csv_data,
                    file_name=f"Nova_扫货决策_{today_str}.csv",
                    mime="text/csv"
                )
            else:
                st.info("未探测到符合条件的标的。")
        else:
            st.error("解析失败！请确保数据列包含：代码、名称、涨跌幅、今日主力净流入。")

st.markdown("""
---
### Nova 的操作说明：
1. **First (初筛)**：寻找资金大幅流入但涨幅平平的板块。
2. **Next (穿透)**：粘贴个股，$E_a$ 越大代表单位波动的吸筹力度越猛。
3. **Finally (确权)**：点击下载 CSV，重点锁定“极品背离”个股。
""")
