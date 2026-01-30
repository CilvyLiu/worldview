import streamlit as st
import pandas as pd
import numpy as np
import re

# ================= 页面配置 =================
st.set_page_config(page_title="嗅嗅 Sniffer - 低价扫货雷达", layout="wide")

# ================= 数据清洗工具 =================
def clean_val(val):
    if pd.isna(val) or val in ['-', '数据', '']: return 0.0
    s = str(val).replace(' ', '').replace(',', '').replace('股吧', '').replace('详情', '')
    mult = 1.0
    if '亿' in s:
        mult = 1e8
        s = s.replace('亿','')
    elif '万' in s:
        mult = 1e4
        s = s.replace('万','')
    if '%' in s:
        mult *= 0.01
        s = s.replace('%','')
    try:
        return float(s) * mult
    except:
        return 0.0

# ================= 核心：正则解析引擎 =================
def parse_sticky_text(text, mode="sector"):
    """针对东财粘连格式的强力解析"""
    rows = []
    lines = text.strip().split('\n')
    
    if mode == "sector":
        # 匹配：序号 + 板块名称 + 涨跌幅(%) + 净额(万/亿) + 净占比(%)
        pattern = re.compile(r'(\d+)\s*([\u4e00-\u9fa5]+).*?(-?\d+\.?\d*%).*?(-?\d+\.?\d*[万亿]).*?(-?\d+\.?\d*%)')
    else:
        # 匹配：序号 + 代码(6位) + 名称 + 价格 + 涨跌幅(%) + 净额(万/亿)
        pattern = re.compile(r'(\d+)\s*(\d{6})\s*([\u4e00-\u9fa5\s]+).*?(\d+\.\d+)\s*(-?\d+\.?\d*%).*?(-?\d+\.?\d*[万亿])')

    for line in lines:
        line = line.strip()
        if not line: continue
        match = pattern.search(line)
        if match:
            rows.append(match.groups())
    return rows

# ================= UI 界面 =================
st.title("🕵️ 嗅嗅 Sniffer - 低价扫货区识别器")
st.markdown(f"> **Nova策略：识别“资金热、股价冷”的背离。** (当前支持粘连文本识别)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("第一步：初筛板块 (First)")
    sector_raw = st.text_area("粘贴板块流向表格", height=200, placeholder="1通信设备大单详情...0.21%20.28亿")

with col2:
    st.subheader("第二步：穿透个股 (Next)")
    stock_raw = st.text_area("粘贴个股流向表格", height=200, placeholder="1002041登海种业...11.2910.04%2.26亿")

# --- 执行嗅探 ---
if st.button("🚀 开始执行 First-Next-Finally 嗅探"):
    if not sector_raw or not stock_raw:
        st.error("Nova，数据缺失，请同时粘贴板块和个股数据。")
    else:
        # 1. 解析板块
        sec_data = parse_sticky_text(sector_raw, mode="sector")
        if sec_data:
            df_sec = pd.DataFrame(sec_data, columns=['序号', '名称', '涨跌幅', '主力净额', '净占比'])
            for c in ['涨跌幅', '主力净额', '净占比']: df_sec[c] = df_sec[c].apply(clean_val)
            st.write("### 📊 板块筛选 (First)")
            st.dataframe(df_sec.sort_values(by='主力净额', ascending=False), use_container_width=True)

        # 2. 解析个股
        stk_data = parse_sticky_text(stock_raw, mode="stock")
        if stk_data:
            df_stk = pd.DataFrame(stk_data, columns=['序号', '代码', '名称', '价格', '涨跌幅', '今日净额'])
            df_stk['名称'] = df_stk['名称'].str.strip()
            for c in ['价格', '涨跌幅', '今日净额']: df_stk[c] = df_stk[c].apply(clean_val)

            # --- 核心判断逻辑 ---
            # Ea因子：流入除以绝对波动，数值越大说明吸筹越隐蔽且高效
            df_stk['Ea'] = df_stk['今日净额'] / (df_stk['涨跌幅'].abs() + 0.01)
            
            df_stk['建议动作'] = "观察中"
            # 💎 极品背离：资金流入 (>0) 且 股价下跌 (<0)
            mask_gold = (df_stk['今日净额'] > 0) & (df_stk['涨跌幅'] < 0)
            df_stk.loc[mask_gold, '建议动作'] = "💎 极品背离 (主力压盘)"
            
            # 🎯 低价扫货：资金流入 (>0) 且 股价波动极小 (-1.5% 到 1.5%)
            mask_ambush = (df_stk['今日净额'] > 0) & (df_stk['涨跌幅'].between(-0.015, 0.015))
            df_stk.loc[mask_ambush & (df_stk['建议动作']=="观察中"), '建议动作'] = "🎯 低价扫货 (爆发临界)"

            # --- 展示结果 ---
            st.divider()
            st.subheader("💰 嗅探结果：低价伏击名单 (Finally)")
            
            res = df_stk[df_stk['建议动作'].str.contains("💎|🎯")].sort_values(by='Ea', ascending=False)
            
            def highlight_status(val):
                if "💎" in val: return 'background-color: #8b0000; color: white'
                if "🎯" in val: return 'background-color: #006400; color: white'
                return ''

            st.dataframe(
                res.style.applymap(highlight_status, subset=['建议动作'])
                         .background_gradient(subset=['Ea'], cmap='YlGnBu'),
                use_container_width=True
            )
            
            # 导出
            st.download_button("📥 导出清单", res.to_csv(index=False).encode('utf-8-sig'), "ambush_list.csv")
            
            st.info("Nova 提示：重点关注 Ea 值极高的标的，那是主力在极窄的空间内完成了巨量换手。")
        else:
            st.warning("未能识别个股数据，请检查粘贴格式是否正确。")
