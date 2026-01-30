import streamlit as st
import pandas as pd
import numpy as np
import re

# ================= 页面配置 =================
st.set_page_config(page_title="嗅嗅 Sniffer - 低价扫货雷达", layout="wide")

# ================= 数据清洗函数 =================
def clean_val(val):
    """统一清洗数字、百分比、亿/万等格式"""
    if pd.isna(val) or val in ['-', '数据', '']:
        return 0.0
    val = str(val).replace(' ', '').replace(',', '').replace('股吧', '').replace('详情', '')
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
    except Exception as e:
        return 0.0

# ================= 文本解析 =================
def parse_em_text(text):
    """用正则匹配序号开头，解析文本表格"""
    rows = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line: continue
        parts = line.split()
        # 识别以数字序号开头的行（如 1, 2, 3...）
        if parts and re.match(r'^\d+', parts[0]):
            rows.append(parts)
    return rows

# ================= UI 界面 =================
st.title("🕵️ 嗅嗅 Sniffer - 低价扫货区识别器")
st.markdown("> **Nova策略：寻找“资金热、股价冷”的静默背离区间。**")

# --- 数据输入 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("第一步：初筛板块 (First)")
    sector_raw = st.text_area("粘贴板块资金流向表格", height=200, placeholder="序号 名称 涨跌幅 今日主力净流入...")

with col2:
    st.subheader("第二步：穿透个股 (Next)")
    stock_raw = st.text_area("粘贴个股资金详情（今日/5日/10日均可）", height=200, placeholder="序号 代码 名称 最新价 涨跌幅 今日主力净流入...")

# --- 执行嗅探 ---
if st.button("🚀 开始嗅探低价扫货区"):
    if not sector_raw or not stock_raw:
        st.error("Nova，数据缺失，请先粘贴东方财富的网页数据。")
    else:
        # -------- 板块初筛 --------
        sec_rows = parse_em_text(sector_raw)
        if len(sec_rows) == 0:
            st.warning("未解析到有效板块数据。")
        else:
            # 索引映射：1:名称, 3:涨跌幅, 4:主力净额, 5:净占比
            df_sec = pd.DataFrame(sec_rows).iloc[:, [1, 3, 4, 5]].copy()
            df_sec.columns = ['名称', '涨跌幅', '主力净额', '净占比']
            for c in ['涨跌幅','主力净额','净占比']:
                df_sec[c] = df_sec[c].apply(clean_val)
            st.subheader("📊 板块初筛结果")
            st.dataframe(df_sec.sort_values(by='净占比', ascending=False), use_container_width=True)

        # -------- 个股穿透 --------
        stk_rows = parse_em_text(stock_raw)
        if len(stk_rows) == 0:
            st.warning("未解析到有效个股数据。")
        else:
            # 索引映射：1:代码, 2:名称, 4:最新价, 5:涨跌幅, 6:今日净额
            df_stk = pd.DataFrame(stk_rows).iloc[:, [1,2,4,5,6]].copy()
            df_stk.columns = ['代码','名称','价格','涨跌幅','今日净额']
            for c in ['价格','涨跌幅','今日净额']:
                df_stk[c] = df_stk[c].apply(clean_val)

            # --- Ea 因子计算 (静默吸筹效率) ---
            # 原理：Ea = 净流入 / (振幅 + 0.01)，寻找波动极小但流入巨大的个股
            df_stk['Ea'] = df_stk['今日净额'] / (df_stk['涨跌幅'].abs() + 0.01)
            df_stk['Ea'] = df_stk['Ea'].clip(upper=1e10)

            # --- 建议动作判定 ---
            df_stk['建议动作'] = "等待信号"
            # 1️⃣ 极品背离：股价跌但资金入
            mask_gold = (df_stk['今日净额'] > 0) & (df_stk['涨跌幅'] < 0)
            df_stk.loc[mask_gold,'建议动作'] = "💎 极品背离 (主力压盘)"
            # 2️⃣ 低价扫货区：横盘震荡但资金入
            mask_ambush = (df_stk['今日净额'] > 0) & (df_stk['涨跌幅'].between(-0.02, 0.02))
            df_stk.loc[mask_ambush & (df_stk['建议动作']=="等待信号"), '建议动作'] = "🎯 低价扫货区 (重点关注)"

            # --- 展示 ---
            st.divider()
            st.subheader("💰 嗅探结果：低价伏击名单")
            # 筛选出有信号的个股并按吸筹效率排序
            best_buys = df_stk[df_stk['建议动作'].str.contains("🎯|💎")].sort_values(by='Ea', ascending=False)

            # 高亮展示函数
            def highlight_status(val):
                if "💎" in val: return 'background-color: #7d1b1b; color: white; font-weight: bold'
                if "🎯" in val: return 'background-color: #1b4d3e; color: white; font-weight: bold'
                return ''

            st.dataframe(
                best_buys.style.applymap(highlight_status, subset=['建议动作'])
                             .background_gradient(subset=['Ea'], cmap='YlGnBu'),
                use_container_width=True
            )

            # --- 导出功能 ---
            csv_data = best_buys.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 导出低价扫货名单 CSV", csv_data, "low_price_sniffer.csv", "text/csv")

            # --- 操作清单 ---
            st.markdown("""
            ### Nova 的操作清单 (First, Next, Finally)：
            1. **First (初筛)**: 观察左侧表格，锁定“净占比”高但“涨跌幅”平淡的板块。
            2. **Next (穿透)**: 查看右侧 $E_a$ 因子。$E_a$ 值越高，代表主力吸筹效率越高且越隐蔽。
            3. **Finally (确权)**: 
                * **💎 极品背离**：主力正在趁着回调或压盘通过“静默期”吸纳廉价筹码。
                * **🎯 低价扫货区**：股价长期横盘不动，主力通过小单缓慢蚕食，即将进入临界爆发点。
            """)
